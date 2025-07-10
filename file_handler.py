import os
from parser import get_signal, get_symbols, check_symbol_patterns
import json
import re

def get_common_folder_files_path():
    home = os.path.expanduser('~')
    directory = os.path.join(home, 'AppData','Roaming','MetaQuotes','Terminal', 'Common', 'Files')
    return directory

def read_from_file(file_path):
    content = ''
    if not os.path.exists(file_path):
        print(f'{file_path} not found')
        return content
    
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    return content

def write_to_file(file_path, content):
    with open(file_path, 'w', encoding='utf-8', errors='ignore') as f:
        f.write(content)


def copy_signal(raw_msg, message_id, sender_id, sender_name="", project_name="", reply_msg="", is_edit=False):
    directory_path = get_common_folder_files_path()
    directory_path = os.path.join(directory_path, project_name, 'Keywords')
   
    for file_name in os.listdir(directory_path):
        keywords = ''
        file_path = os.path.join(directory_path, file_name)
        if os.path.isfile(file_path):
            try:
                keywords = get_keywords(file_path)
                print('Getting signal for file: ', file_name)
                signal = get_signal(raw_msg, keywords)
                
                if signal == '':
                    continue
                
                symbol_path = os.path.join(directory_path.replace('Keywords', 'Symbols'), file_name)

                if os.path.exists(symbol_path):
                    if reply_msg == "":
                        signal['symbol'] = check_symbol_patterns(raw_msg, symbol_path)
                    else:
                        signal['symbol'] = check_symbol_patterns(reply_msg, symbol_path)

                signal["sender_name"] = sender_name
                signal['sender_id'] = sender_id
                signal['message_id'] = message_id
                signal['is_edit'] = is_edit
                print('=========================')
                print('Signal: ',signal)
                print('=========================')
                destination_dir = directory_path.replace('Keywords', 'Signals')
                os.makedirs(destination_dir, exist_ok=True)
                destination_path = os.path.join(destination_dir, file_name)
                write_to_file(destination_path, json.dumps(signal))
            except Exception as e:
                print(f"Could not read {file_name}: {e}")


def get_keywords(file):
    keywords = read_from_file(file_path=file)
    return keywords

