import re
import json

def check_signal_patterns(signal_text, keywords):
    signal_text_lower = signal_text.lower()
    signal_text_lower = signal_text_lower.replace('**', '')
    signal_text_lower = signal_text_lower.replace('##', '')
    signal_text_lower = signal_text_lower.replace('__', '')
    #print('Signal text cleaned: ',signal_text_lower)
    patterns_found = {}
    
    for key, patterns in keywords.items():
        patterns_found[key] = list()
        pattern_list = patterns.split(',')
        # Sort patterns by length to prioritize longer matches
        pattern_list = sorted(pattern_list, key=len, reverse=True)
        
        
        for pattern in pattern_list:
            pattern = pattern.strip()
            # Handle placeholder patterns with [X] dynamically
            if "[X]" in pattern:    
                # Replace [X] with a regex pattern for text followed by digits
                replacement = re.escape(pattern).replace(r'\[X\]', r'\d+')
                regex_pattern = re.compile(
                    replacement, re.IGNORECASE
                )
            
            elif "[x]" in pattern:    
                # Replace [X] with a regex pattern for text followed by digits
                replacement = re.escape(pattern).replace(r'\[x\]', r'\d+')
                regex_pattern = re.compile(
                    replacement, re.IGNORECASE
                )
                
            else:
                # Escape literal patterns for regex
                regex_pattern = re.compile(re.escape(pattern), re.IGNORECASE)

            if key in ['EntryPointKeywords', 'TakeProfitKeywords', 'NewTakeProfitKeywords', 'StopLossKeywords', 'NewStopLossKeywords', 'LotSizeKeywords', 'UpdateTPKeywords', 'UpdateSLKeywords', 'ModifyOrderKeywords']:
                number_regex = r"(?<=\W|_)([0-9]+\.[0-9]+|[0-9]{2,})(\s*-\s*([0-9]+\.[0-9]+|[0-9]{2,}))?(?=\s|$)"
#r"(?<=\W)[0-9]+(?:\.[0-9]+)?(?:\s*-\s*[0-9]+(?:\.[0-9]+)?)?(?=\s|\n)"
                num_regex = r'([0-9]+\.[0-9]+|[0-9]{2,})'
                conjoined_pattern = rf'({pattern.lower()})({num_regex})'
                signal_text_lower = re.sub(conjoined_pattern, r"\1 \2", signal_text_lower)
                matches = regex_pattern.finditer(signal_text_lower)
                
                
                for match in matches:
                    # Get the found text for the pattern
                    found_text = match.group(0)

                    

                    # Look for a contiguous number (price/pips/points) after the pattern
                    #following_number_match = re.search(number_regex, signal_text_lower[match.end():])
                    text_block = signal_text_lower[match.span()[0]:].split("\n", 1)[0]
                    text_block = re.sub(r'\sPips', 'pips', text_block, flags=re.IGNORECASE)
                    print('Block: ',text_block)
                    if key == 'TakeProfitKeywords':
                        if len(text_block.split(' ')) <= 2:
                            following_number_match = re.search(
                                number_regex, 
                                text_block
                            )
                        else:
                            following_number_match = re.findall(
                                number_regex,
                                text_block
                            )
                    else:
                        following_number_match = re.search(
                                number_regex, 
                                text_block
                            )
                    
                    if key == 'LotSizeKeywords':
                        print('Following number: ',following_number_match)
                        
                    if not following_number_match:
                        following_number_match = re.search(
                            number_regex, 
                            signal_text_lower[signal_text_lower.find(pattern):]
                        )
                   
                    if following_number_match:
                        if isinstance(following_number_match, list):
                            match_list = []
                            for _match in following_number_match:
                                match_list.append(_match[0])
                            value = match_list   
                        else:
                            value = following_number_match.group(0)  
                       
                        patterns_found[key].append((found_text, value))
                    # else:
                    #     patterns_found[key].append((found_text, 0))
                
        
            else:
                matched = regex_pattern.search(signal_text_lower)
                if matched:
                    patterns_found[key].append(matched.group(0))
            
            if len(patterns_found[key]) > 0:
                break
        
        if patterns_found[key] == []:
            del patterns_found[key]
        
                

    return patterns_found


def new_entry_signal(patterns_found):
    print('Patterns: ',patterns_found)
    entry = patterns_found.get('EntryPointKeywords', False)
    tps = patterns_found.get('TakeProfitKeywords', False)
    sl = patterns_found.get('StopLossKeywords', False)
    lots = patterns_found.get('LotSizeKeywords', False)
    buylimit = patterns_found.get('BuyLimitKeywords', False)
    selllimit = patterns_found.get('SellLimitKeywords', False)
    buystop = patterns_found.get('BuyStopKeywords', False)
    sellstop = patterns_found.get('SellStopKeywords', False)
    buy = patterns_found.get('BuyKeywords', False)
    sell = patterns_found.get('SellKeywords', False)
    
    signal_map = {
    'BUYLIMIT': buylimit,
    'SELLLIMIT': selllimit,
    'BUYSTOP': buystop,
    'SELLSTOP': sellstop,
    'BUY': buy,
    'SELL': sell
    }
    
    signal = dict()
    signal['mode'] = 'ENTRY'
    signal['type'] = next((key for key, value in signal_map.items() if value), None)
    signal['entry_price'] = entry[0][1] if entry else 'MARKET'
    
    signal['stop_loss'] = sl[0][1] if sl else 0
    signal['take_profits'] = []
    signal['lot_size'] = lots[0][1] if lots else 0
    
    if tps:
        one_line_tp = len(tps) == 1
        for tp in tps:
            tp_value = tp[1]
            if isinstance(tp_value, list):
                if one_line_tp:
                    signal['take_profits'].extend(tp_value)
                else:
                    signal['take_profits'].append(tp_value[0])
            else:
                signal['take_profits'].append(tp[1])
            
    return signal if signal['type'] is not None else ''

def new_exit_signal(patterns_found):
    # Extract keywords from patterns_found
    closetp = patterns_found.get('CloseTPKeywords', False)
    closeorder = patterns_found.get('CloseOrderKeywords', False)
    cancelorder = patterns_found.get('CancelOrderKeywords', False)
    closeallorders = patterns_found.get('CloseAllOrdersKeywords', False)
    cancelallpending = patterns_found.get('CancelAllPendingKeywords', False)
    delete = patterns_found.get('DeleteKeywords', False)
    
    # Map keywords to actions
    action_map = {
        'CLOSE_ALL_ORDERS': closeallorders,
        'CANCEL_ALL_PENDING': cancelallpending,
        'CLOSE_TP': closetp,
        'CLOSE_ORDER': closeorder,
        'CANCEL_ORDER': cancelorder,
        'DELETE': delete
    }
    
    # Initialize the signal dictionary
    signal = {
        'mode' : 'EXIT',
        'type': next((key for key, value in action_map.items() if value), None),
        'target_index': ''
    }
    
    # Populate action details if applicable
    if signal['type'] == 'CLOSE_TP' and closetp:
        match = re.search(r'(\d+)', closetp[0])
        if match:
            signal['target_index'] = int(match.group(1))
    
    if signal['type'] == 'CLOSE_ALL_ORDERS' and closeallorders:
        signal['target_index'] = 'all'
    
    if signal['type'] == 'CANCEL_ALL_PENDING' and cancelallpending:
        signal['target_index'] = 'pending'
    
    if signal['type'] == 'CANCEL_ORDER' and cancelorder:
        signal['target_index'] = 'pending'
    
    if signal['type'] == 'CLOSE_ORDER' and closeorder:
        signal['target_index'] = 'open'
    
    if signal['type'] == 'DELETE' and delete:
        signal['target_index'] = 'pending'
    
    # Return the signal only if an action type is found
    return signal if signal['type'] is not None else ''

    
def new_modify_signal(patterns_found):
    # Extract keywords from patterns_found
    modifyorder = patterns_found.get('ModifyOrderKeywords', False)
    breakeven = patterns_found.get('BreakevenKeywords', False)
    updatesl = patterns_found.get('UpdateSLKeywords', False)
    updatetp = patterns_found.get('UpdateTPKeywords', False)
    newsl = patterns_found.get('NewStopLossKeywords', False)
    newtp = patterns_found.get('NewTakeProfitKeywords', False)
    closepartial = patterns_found.get('ClosePartialKeywords', False)
    closehalf = patterns_found.get('CloseHalfKeywords', False)
    
    # Map keywords to actions
    action_map = {
        'BE_AND_PC': breakeven and closepartial,
        'MODIFY_ORDER': modifyorder,
        'BREAKEVEN': breakeven,
        'UPDATE_SL': updatesl,
        'UPDATE_TP': updatetp,
        'NEW_SL': newsl,
        'NEW_TP': newtp,
        'CLOSE_PARTIAL': closepartial,
        'CLOSE_HALF': closehalf,
    }
    
    # Initialize the signal dictionary
    signal = {
        'mode' : 'MODIFY',
        'type': next((key for key, value in action_map.items() if value), None),
        'target_index': [],
        'new_value': []
    }
    
    # Populate action details if applicable
    if signal['type'] == 'MODIFY_ORDER' and modifyorder:
        command = modifyorder[0][0]
        tp_cmds = [r'tp\d*', r'take profit\s*\d*', r'takeprofit\s*\d*', r'target\s*\d*']
        sl_cmds = ['sl', 'stop loss', 'stoploss']
        found_pattern = ''

        for cmd in tp_cmds:
            if re.search(cmd, command.lower()):
                found_pattern = cmd
                signal['subtype'] = 'TP'
                break
        
        for cmd in sl_cmds:
            if cmd in command.lower():
                signal['subtype'] = 'SL'
                break
        
        for cmd in modifyorder:
            match = re.search(r'(\d+)', cmd[0])
            if match:
                signal['target_index'].append(int(match.group(1)))
            signal['new_value'].append(cmd[1])
        
       
    if signal['type'] == 'UPDATE_TP' and updatetp:
        for tp in updatetp:
            match = re.search(r'(\d+)', tp[0])
            if match:
                signal['target_index'].append(int(match.group(1)))
            signal['new_value'].append(tp[1])
        
    if signal['type'] == 'NEW_TP' and newtp:
        for tp in newtp:
            match = re.search(r'(\d+)', tp[0])
            if match:
                signal['target_index'].append(int(match.group(1)))
            signal['new_value'].append(tp[1])
    
    if signal['type'] == 'UPDATE_SL' and updatesl:
        signal['target_index'] = 'all'
        signal['new_value'] = updatesl[0][1]
    
    if signal['type'] == 'NEW_SL' and newsl:
        signal['target_index'] = 'all'
        signal['new_value'] = newsl[0][1]
    
    if signal['type'] == 'BREAKEVEN' and breakeven:
        signal['target_index'] = 'all'
    
    # if signal['type'] == 'MODIFY_ORDER' and modifyorder:
    #     signal['target_index'] = 'all'
    #     signal['new_value'] = modifyorder[0][1]
    
    if signal['type'] == 'CLOSE_PARTIAL' and closepartial:
        signal['target_index'] = 'all'
    
    if signal['type'] == 'CLOSE_HALF' and closehalf:
        signal['target_index'] = 'all'
    
    # Return the signal only if a modify type is found
    return signal if signal['type'] is not None else ''

def new_exception_signal(patterns_found):
    return True if patterns_found.get('ExceptionKeywords', None) is not None else False

def get_symbols(symbol_file):
    symbols = ''
    with open(symbol_file, 'r', encoding='utf-8', errors='ignore') as f:
        symbols = f.read()
    return symbols

def check_symbol_patterns(signal_text, symbol_file):
    def get_symbols(symbol_file):
        with open(symbol_file, 'r') as file:
            return file.read()
    
    signal_text_copy = signal_text
    signal_text_copy = signal_text_copy.replace('**', '')
    signal_text_copy = signal_text_copy.replace('##', '')
    signal_text_copy = signal_text_copy.replace('__', '')
    
    signal_text_copy = re.sub(r'([a-zA-Z]+)/([a-zA-Z]+)', r'\1\2', signal_text_copy)
    
    symbols = get_symbols(symbol_file)
    symbol_list = [symbol.strip() for symbol in symbols.split(',')]
    
    for symbol in symbol_list:
        pattern = rf"\b{re.escape(symbol)}\b"
        if re.search(pattern, signal_text_copy, re.IGNORECASE):
            return symbol
    
    return None


def get_signal(signal_text, keywords):
    keywords_json = json.loads(keywords)
    patterns_found = check_signal_patterns(signal_text=signal_text, keywords=keywords_json)
    entry = new_entry_signal(patterns_found=patterns_found)
    modify = new_modify_signal(patterns_found=patterns_found)
    exit = new_exit_signal(patterns_found=patterns_found)
    exception = new_exception_signal(patterns_found=patterns_found)

    check = entry if entry else modify if modify else exit
    
    return check if not exception else {"mode": "IGNORE"}


# msg = '''
# BUY BITCOIN at 98000

# 🔒TARGET 1 : 10000 points
# 🔒TARGET 2 : 20000 points

# SL: 30000 points
# '''


# keywords = '''
# {"ExceptionKeywords":"report,result,summary","EntryPointKeywords":"at,price,entry,@,now,zone,price @,open order,buy now,sell now,new signal,new order,trade","StopLossKeywords":"stop loss,stop-loss,stoploss,sl,sl@,s\/l","NewStopLossKeywords":"sl[X] ->, stoploss[X] ->, sl to","TakeProfitKeywords":"take profit,take-profit,takeprofit,tp,tp@,t\/p,target","NewTakeProfitKeywords":"tp[X] ->, takeprofit[X] ->, tp to, tp[X] to, target [X]","BuyKeywords":"buy,long","SellKeywords":"sell,short,a sell","BuyLimitKeywords":"buy limit,buy-limit,buylimit","SellLimitKeywords":"sell limit,sell-limit,selllimit","BuyStopKeywords":"buy stop,buy-stop,buystop","SellStopKeywords":"sell stop,sell-stop,sellstop","CloseTPKeywords":"Close TP1,Close TP2,Close TP3,Close TP4,Close TP5","CloseOrderKeywords":"Close,close order,stoploss order,takeprofit order,order tp,order sl,close [X] pips","CancelOrderKeywords":"cancel order,order canceled","CloseAllOrdersKeywords":"close all positions,close all orders","ModifyOrderKeywords":"modify order,modify tp,modify sl,set tp,move sl,move tp,change sl,change tp","CancelAllPendingKeywords":"cancel all pending","DeleteKeywords":"Delete","BreakevenKeywords":"Move to breakeven,breakeven,sl to entry,stoploss to entry","UpdateSLKeywords":"Update Stoploss","UpdateTPKeywords":"Update TP1,Update TP2,Update TP3,Update TP4,Update TP5","ClosePartialKeywords":"close partial,partial close","CloseHalfKeywords":"close half"}
# '''

# print(get_signal(msg, keywords))