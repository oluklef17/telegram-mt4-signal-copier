
import sys
import os
import sqlite3
import json
import asyncio
import logging
from datetime import datetime, date
from queue import Queue

from telethon import TelegramClient, events, utils
import telethon.errors as errors
from telethon.tl.types import User, Channel, Chat

from image_reader import extract_text_from_video

from file_handler import copy_signal

from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import (
    QApplication, QWidget, QMainWindow, QDialog, QLabel, QLineEdit, QCheckBox, QPushButton,
    QVBoxLayout, QHBoxLayout, QComboBox, QListWidget, QStackedWidget, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPalette, QBrush, QPixmap, QFont

def show_admin_message():
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Critical)
    msg.setText("Permission Denied")
    msg.setInformativeText("Please restart the application and run as administrator")
    msg.setWindowTitle("Error")
    msg.exec_()

try:
    os.makedirs('LOGS', exist_ok=True)
    time = str(datetime.now().strftime('%Y-%m-%d'))
    logging.basicConfig(filename=os.path.join('LOGS',f'{time}.log'),
                        format='%(asctime)s %(message)s',
                        filemode='a')
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
except PermissionError:
    show_admin_message()

client = None
session = 'user'
api_id = 0 #YOUR API ID
api_hash = "YOUR API HASH"

client_logged_in = False

all_chats = {}
selected_chats = {}

loop = asyncio.get_event_loop()

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Echotrade Telegram Copier")
        self.resize(600, 400)
        self.setWindowIcon(QtGui.QIcon(resource_path('ETC.ico')))

        self.setFixedSize(650, 350)
        self.set_background_image(resource_path("ETC.png"))
           
        #Font
        QtGui.QFontDatabase.addApplicationFont(resource_path('poppins.ttf'))
        self.font = QtGui.QFont()
        self.font.setFamily('Poppins')

        

        selected_chats

        # Create stacked widget
        self.stacked_widget = QStackedWidget()

        # Create pages
        self.login_page = LoginPage()
        self.main_page = MainPage()
        self.loading_page = LoadingPage()

        # Add pages to stacked widget
        self.stacked_widget.addWidget(self.login_page)
        self.stacked_widget.addWidget(self.main_page)
        self.stacked_widget.addWidget(self.loading_page)

        # Set initial page
        self.setCentralWidget(self.stacked_widget)
        self.stacked_widget.setCurrentWidget(self.login_page)

        self.set_font()

        self.show_loading_page()

        # Connect signals to switch pages
        self.login_page.login_successful.connect(self.show_main_page)
        self.login_page.login_init.connect(self.show_login_page)
        self.main_page.logout_requested.connect(self.show_login_page)
    
    def set_font(self):
        for child_widget in self.stacked_widget.findChildren(QWidget):
            try:
                child_widget.setFont(self.font)
            except Exception as e:
                print(f"Could not set font. Reason: ",e)

    def show_main_page(self):
        self.stacked_widget.setCurrentWidget(self.main_page)

    def show_login_page(self):
        self.stacked_widget.setCurrentWidget(self.login_page)
    
    def show_loading_page(self):
        self.stacked_widget.setCurrentWidget(self.loading_page)

    def set_background_image(self, image_path):
        # Create a QPalette and set a QBrush with the background image
        palette = QPalette()
        pixmap = QPixmap(image_path)
        brush = QBrush(pixmap)
        palette.setBrush(QPalette.Window, brush)
        self.setPalette(palette)

class LoadingPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)

        self.label = QLabel("LOADING...")
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)

        self.setLayout(layout)

class LoginPage(QWidget):
    login_successful = QtCore.pyqtSignal(str)
    login_init = QtCore.pyqtSignal(str)

    global loop

    def __init__(self):
        super().__init__()
       
        self.loop = loop
        self.from_gui = Queue()
        self.from_tg = Queue()
        self.worker = TelegramLoginWorker(self.loop, self, from_tg=self.from_tg, from_gui=self.from_gui)
        self.worker.signal.connect(self.handle_tg_signal)
        self.worker.start()

        self.state = 'phone'

        self.label = QLabel("Enter your phone number with + country code:")
        self.line_edit = QLineEdit()
        self.line_edit.setPlaceholderText("+380 500174144")
        self.next_button = QPushButton("Next")
        today = date.today()
        year = str(today.year)
        self.footer_label = QLabel("")
        self.footer_label.setAlignment(Qt.AlignCenter)

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.line_edit)
        layout.addWidget(self.next_button)
        layout.addWidget(self.footer_label)

        self.setLayout(layout)

        self.next_button.clicked.connect(self.send_to_tg)

    def handle_tg_signal(self, msg):
        if msg == 'success':
            self.login_successful.emit(msg)
        elif msg == 'logout':
            self.login_init.emit(msg)
        else:
            self.set_state(msg)

    def set_state(self, state):
        self.state = state
        self.line_edit.clear()
        if state == "phone":
            self.label.setText("Enter your phone number with + country code:")
            self.line_edit.setEchoMode(QLineEdit.Normal)
            self.line_edit.setPlaceholderText("+380 500174144")
        elif state == "code":
            self.label.setText("Enter the code received from Telegram:")
            self.line_edit.setEchoMode(QLineEdit.Normal)
            self.line_edit.setPlaceholderText("12345")
        elif state == "password":
            self.label.setText("You have 2FA enabled. Enter your Telegram password:")
            self.line_edit.setEchoMode(QLineEdit.Password)
            self.line_edit.setPlaceholderText("Password")

    def send_to_tg(self):
        next_state = {'phone': 'code', 'code': 'login', 'password': 'password'}
        print('Next state: ',next_state.get(self.state, ''))
        self.from_gui.put(next_state.get(self.state, ''))

class MainPage(QWidget):
    logout_requested = QtCore.pyqtSignal(str)
    global loop

    def __init__(self):
        super().__init__()

        self.loop = loop
        self.to_tg = Queue()
        # Assume TelegramMainWorker is defined elsewhere
        self.worker = TelegramMainWorker(self.loop, self, self.to_tg)
        self.worker.signal.connect(self.handle_tg_signal)
        self.worker.start()

        self.channel_label = QLabel("Select channel/chat")
        self.channel_combobox = QComboBox()
        self.channel_combobox.addItem('SELECT CHANNEL/CHAT')

        self.channel_list = QListWidget()
        self.add_button = QPushButton("Add")
        self.delete_button = QPushButton("Delete")
        self.refresh_button = QPushButton("Refresh")
        self.logout_button = QPushButton("Log Out")
        today = date.today()
        year = str(today.year)
        self.footer_label = QLabel(f"")
        self.footer_label.setAlignment(Qt.AlignCenter)

        list_layout = QVBoxLayout()
        button_layout = QVBoxLayout()
        footer_layout = QVBoxLayout()

        list_layout.addWidget(self.channel_list)
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.delete_button)
        button_layout.addWidget(self.refresh_button)
        button_layout.addWidget(self.logout_button)

        footer_layout.addWidget(self.footer_label)

        layout_wrapper = QHBoxLayout()
        layout_wrapper.addLayout(list_layout, stretch=2)
        layout_wrapper.addLayout(button_layout, stretch=1)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.channel_label)
        main_layout.addWidget(self.channel_combobox)
        main_layout.addLayout(layout_wrapper)
        main_layout.addStretch()
        main_layout.addLayout(footer_layout)

        self.setLayout(main_layout)

        self.load_channels()

        self.add_button.clicked.connect(self.add_channel)
        self.delete_button.clicked.connect(self.delete_channel)
        self.refresh_button.clicked.connect(self.refresh_channels)
        self.logout_button.clicked.connect(self.logout)

    def handle_tg_signal(self, msg):
        if msg == 'logout':
            self.logout_requested.emit(msg)

    def add_channel(self):
        current_chat = self.channel_combobox.currentText()
        current_chat_id = str(all_chats[current_chat]).replace('-100', '')

        items = [self.channel_list.item(x).text() for x in range(self.channel_list.count())]

        if f'{current_chat_id} ☐ {current_chat}' in items or current_chat.lower().find('select chats') != -1:
            return

        selected_chats[current_chat] = all_chats.get(current_chat, 0)
        
        items.append(f'{current_chat_id} ☐ {current_chat}')
        self.channel_list.clear()
        self.channel_list.addItems(items)
        print('Selected: ', selected_chats)

        # Save the updated channel list to a file
        try:
            with open('selected_channels.txt', 'w', encoding='utf-8', errors='ignore') as f:
                for item in items:
                    f.write(f"{item}\n")
        except PermissionError:
            show_admin_message()
    
    def load_channels(self):
        if not os.path.exists('selected_channels.txt'):
            return
        try:
            with open('selected_channels.txt', 'r', encoding='utf-8', errors='ignore') as f:
                for line in f.readlines():
                    current_chat = line.split('☐')[1].strip()
                    selected_chats[current_chat] = int(line.split('☐')[0].strip())
                    self.channel_list.addItem(line.strip())
        except PermissionError:
            show_admin_message()
        

    def delete_channel(self):
        current_item = self.channel_list.currentItem()
        deleted = ''
        for i in range(self.channel_list.count()):
            if str(self.channel_list.item(i).text()) == current_item.text():
                deleted = str(self.channel_list.item(i).text())
                self.channel_list.takeItem(i)
                break
        
        chat_to_pop = ''

        for chat, id in selected_chats.items():
            if deleted == '':
                break
            if deleted.find(chat) != -1:
                chat_to_pop = chat
                break
        
        if chat_to_pop != '':
            selected_chats.pop(chat_to_pop)

        print('Selected: ', selected_chats)

        # Save the updated channel list to a file
        items = [self.channel_list.item(x).text() for x in range(self.channel_list.count())]
        try:
            with open('selected_channels.txt', 'w', encoding='utf-8', errors='ignore') as f:
                for item in items:
                    f.write(f"{item}\n")
        except PermissionError:
            show_admin_message()



    def refresh_channels(self):
        logger.info('Chat list refresh button clicked.')
        self.to_tg.put('chats')

    def logout(self):
        logger.info('Logout button clicked')
        self.to_tg.put('logout')

class TelegramMainWorker(QtCore.QThread):
    signal = QtCore.pyqtSignal(str)

    def __init__(self, loop, gui, from_gui):
        super().__init__()
        self.loop = loop
        self.from_gui = from_gui
        self.gui = gui
        self.new_message = ''
    
    async def fetch_gui_command(self):
        while True:
            await asyncio.sleep(1)

            try:
                if not self.from_gui.empty():
                    self.new_message = self.from_gui.get()
                    print(f'New command received: {self.new_message}')
            except Exception as e:
                logger.error(f'Some error occured while fetching GUI command. ({e})')
    
    async def reconnect_client_if_needed(self):
        global client, client_logged_in

        if not client_logged_in:
            return

        if client is None:
            client = TelegramClient(session=session, api_id=api_id, api_hash=api_hash)

        if not client.is_connected():
            await client.connect()

    async def load_chats(self):
        global all_chats, client, session, api_id, api_hash
        while all_chats == {}:
            await asyncio.sleep(1)
            
            try:
                await self.reconnect_client_if_needed()

                if await client.is_user_authorized():
                    async for dialog in client.iter_dialogs():
                        if not dialog.is_user:
                            self.gui.channel_combobox.addItem(dialog.title)

                            if all_chats.get(dialog.title, None) is None:
                                all_chats[dialog.title] = int(str(dialog.entity.id).replace('-100', '').replace('-', ''))
                          
                if len(all_chats) > 0:
                    logger.info('Chats initialized successfully')
                    break

            except sqlite3.OperationalError:
                logger.warning('Database is locked hence cannot load chats. Will retry...')
            except Exception as e:
                logger.error(f'Some error occured while loading chats. ({e})')
    
    async def refresh_chats(self):
        global all_chats, client, session, api_id, api_hash
        while True:
            await asyncio.sleep(1)
            
            try:
                if self.new_message != 'chats':
                    continue

                self.new_message = ''

                await self.reconnect_client_if_needed()

                if await client.is_user_authorized():
                    self.gui.channel_combobox.clear()
                    all_chats.clear()
                    self.gui.channel_combobox.addItem('SELECT CHANNEL/CHAT')
                    async for dialog in client.iter_dialogs():
                        if not dialog.is_user:
                            self.gui.channel_combobox.addItem(dialog.title)

                            if all_chats.get(dialog.title, None) is None:
                                all_chats[dialog.title] = int(str(dialog.entity.id).replace('-100', '').replace('-', ''))
                            
            except sqlite3.OperationalError:
                logger.warning('Database is locked hence cannot refresh chats.')
            except Exception as e:
                logger.error(f'Some error occured while refreshing chats. ({e})')
    
    async def register_event_handlers(self):
        global client, client_logged_in
        while not client_logged_in:
            if client_logged_in:
                break
            await asyncio.sleep(1)
        
        @client.on(events.NewMessage())
        async def new_msg_handler(event):
            try:
                message = event.text
                chat = await event.get_chat()
                sender_entity = await event.get_sender()
                
                if isinstance(chat, User):
                    return
                
                #print(chat)
               
                reply_msg = ''
                message_id = event.id
                if event.is_reply:
                    reply = await event.get_reply_message()
                    reply_msg = reply.text
                    message_id = reply.id
                    
                sender_id = chat.id
                
                if sender_id not in list(selected_chats.values()):
                    print(f'Sender with ID {sender_id} not in selected chats/channels')
                    return

                copy_signal(message, message_id, sender_id, chat.title, "EchoTrade Telegram Copier", reply_msg=reply_msg)
            except Exception as e:
                logger.error(f"Failed to process last message. Reason: {e}")
        
        @client.on(events.MessageEdited)
        async def edited_msg_handler(event):
            try:
                message = event.text
                chat = await event.get_chat()
                sender_entity = await event.get_sender()
                
                if isinstance(chat, User):
                    return
                
                #print(chat)
               
                reply_msg = ''
                message_id = event.id
                if event.is_reply:
                    reply = await event.get_reply_message()
                    reply_msg = reply.text
                    message_id = reply.id
                    
                sender_id = chat.id
                
                if sender_id not in list(selected_chats.values()):
                    print(f'Sender with ID {sender_id} not in selected chats/channels')
                    return

                copy_signal(message, message_id, sender_id, chat.title, "EchoTrade Telegram Copier", reply_msg=reply_msg, is_edit=True)
            except Exception as e:
                logger.error(f"Failed to process last message. Reason: {e}")
        

    
    async def run_client(self):
        global client, client_logged_in

        while not client_logged_in:
            if client_logged_in:
                break
            await asyncio.sleep(1)

        try:
            await client.start()
            await client.run_until_disconnected()
        except asyncio.CancelledError:
            logger.info("Session was terminated.")
        except ConnectionError:
            logger.error("Disconnected from Telegram. Please check your connection and restart the application.")           
        except Exception as e:
            logger.error(f"Failed to run client. Reason: {e}")
    
    async def logout(self):
        global client, session, api_id, api_hash
        while True:
            await asyncio.sleep(1)

            try:
                if self.new_message != 'logout':
                    continue
               
                self.new_message = ''
                
                await self.reconnect_client_if_needed()

                if await client.is_user_authorized():
                    logger.info('Logging out Telegram client...')
                    await client.log_out()

                self.signal.emit('logout')
               
            except sqlite3.OperationalError:
                logger.warning('Database is locked hence cannot log out. Will retry...')
            except Exception as e:
                logger.error(f'Some error occured while logging out. ({e})')
    

                
    async def main(self):
        await asyncio.gather(
            self.load_chats(),
            self.refresh_chats(),
            self.logout(),
            self.fetch_gui_command(),
            self.register_event_handlers(),
            self.run_client()
        )
    
    def run(self):
        global loop
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.main())
        except Exception as e:
            logger.error(f"An error occurred: {e}")
        

class TelegramLoginWorker(QtCore.QThread):
    signal = QtCore.pyqtSignal(str)

    def __init__(self, loop, gui, from_tg, from_gui):
        super().__init__()
        self.loop = loop
        self.gui = gui
        self.from_gui = from_gui
        self.from_tg  = from_tg
    
        
    async def login(self):
        global client, client_logged_in, session, api_id, api_hash
        success = False
        phone = ''
        phone_code_hash = None
        while True:
            await asyncio.sleep(1)
            try:
                if client is None:
                    client = TelegramClient(session=session, api_id=api_id, api_hash=api_hash)
                    await client.connect()

                if await client.is_user_authorized():
                    success = True
                    client_logged_in = True
                    self.signal.emit('success')
                    break
                else:
                    self.signal.emit('logout')
                    
                    if not self.from_gui.empty():
                        new_message = self.from_gui.get()

                        print('New message: ',new_message)

                        if new_message == 'code':
                            phone = self.gui.line_edit.text()
                            print('Phone is: ',phone)
                            result = await client.send_code_request(phone)
                            phone_code_hash = result.phone_code_hash

                            self.signal.emit('code')
                        
                        if new_message == 'login':
                            code = self.gui.line_edit.text()
                            try:
                                await client.sign_in(phone=str(phone), code=str(code), phone_code_hash=str(phone_code_hash))
                                self.signal.emit('main')
                               
                            except errors.SessionPasswordNeededError:
                                self.signal.emit('password')

                        if new_message == 'password':
                            pwd = self.gui.line_edit.text()
                            await client.sign_in(password=str(pwd))
                    
                    success = await client.is_user_authorized()

                    if success:
                        logger.info('Client is logged in.')
                        client_logged_in = True
                        self.signal.emit('success')
                        break
                    # else:
                    #     print('Client login failed. Please try again.')
            
            except sqlite3.OperationalError:
                logger.warning('Database is locked hence cannot log in. Will retry...')
            except Exception as e:
                logger.error(f'Some error occured while logging in. ({e})')

        return client, success

    def run(self):
        global loop
        # loop = asyncio.get_event_loop()
        asyncio.set_event_loop(loop)
        asyncio.ensure_future(self.login())   
        

if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    app.setWindowIcon(QtGui.QIcon(resource_path('ETC.ico')))
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
