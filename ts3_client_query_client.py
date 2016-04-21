import html
import re
import sys
import telnetlib

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QThread
from PyQt5.QtWidgets import QApplication, QMainWindow

import mainwindow

clients = {}
channels = {}
speakers_text = []
text_messages_text = []
connection = telnetlib.Telnet()
target_ip_addr = '192.168.1.2'
target_port = 25639

debug = False

replace_list = [
    ('\\', r'\\'),
    ('/', r'\/'),
    (' ', r'\s'),
    ('|', r'\p'),
    ('\a', r'\a'),
    ('\b', r'\b'),
    ('\f', r'\f'),
    ('\n', r'\n'),
    ('\r', r'\r'),
    ('\t', r'\t'),
    ('\v', r'\v')
]

notify_events = [
    'notifytalkstatuschange',
    'notifytextmessage',
    'notifycurrentserverconnectionchanged',
    'notifyclientmoved',
    'notifycliententerview',
    'notifyclientleftview',
    'notifyclientpoke',
    'notifyclientupdated',
    'notifychanneledited'
]

my_clid = ''
my_cid = ''

data_queue = []

class Main(QObject):

    speakeron_event = pyqtSignal([str])
    speakeroff_event = pyqtSignal([str])
    display_text_event = pyqtSignal([str])
    text_message_event = pyqtSignal([str,str,str])

    def main(self):

        self.speakeron_event.connect(append_speakers_text)
        self.speakeroff_event.connect(remove_speakers_text)
        self.display_text_event.connect(display_message)
        self.text_message_event.connect(text_message)

        thread.start()

        ui.lineEdit.returnPressed.connect(send_text_message)

        app.exec()
        thread.breakflag = True

class TelnetThread(QThread):

    breakflag = False

    @staticmethod
    def handle_data():

        global my_cid,my_clid

        while len(data_queue) > 0:
            text = data_queue.pop(0)

            if text.startswith('notifytalkstatuschange '):
                clid = get_param(text, 'clid')

                if clid not in clients.keys():
                    if update_client_list() != 0:
                        print('ERROR [handle_data]: error updating client list while handling notifytalkstatuschange!')
                        continue

                if 'status=1' in text:
                    main.speakeron_event.emit(clients[clid][0])
                elif 'status=0' in text:
                    main.speakeroff_event.emit(clients[clid][0])

            elif text.startswith('notifytextmessage '):

                name = ts_replace(get_param(text, 'invokername'))
                message = ts_replace(get_param(text, 'msg'))
                mode = get_param(text, 'targetmode')

                main.text_message_event.emit(name, message, mode)

            elif text.startswith('notifycurrentserverconnectionchanged '):
                if update_client_list() != 0:
                    print('ERROR [handle_data]: error updating client list while handling notifycurrentserverconnectionchanged!')
                if update_channel_list() != 0:
                    print('ERROR [handle_data]: error updating channel list while handling notifycurrentserverconnectionchanged!')
                if whoami() != 0:
                    print('ERROR [handle_data]: error updating whoami while handling notifycurrentserverconnectionchanged!')

            elif text.startswith('notifyclientmoved '):
                clid = get_param(text, 'clid')
                ctid = get_param(text, 'ctid')

                if my_cid == '' or my_clid == '':
                    if whoami() != 0:
                        print('ERROR [handle_data]: error updating whoami while handling notifyclientmoved!')
                        continue

                if clid not in clients.keys():
                    if update_client_list() != 0:
                        print('ERROR [handle_data]: error updating client list while handling notifyclientmoved!')
                        continue

                if ctid not in channels.keys():
                    if update_channel_list() != 0:
                        print('ERROR [handle_data]: error updating channel list while handling notifyclientmoved!')
                        continue

                if clid == my_clid:
                    main.display_text_event.emit('You moved to channel <b>' + html.escape(channels[ctid]) + '</b>')
                    if whoami() != 0:
                        print(print('ERROR [handle_data]: error updating whoami while handling notifyclientmoved!'))
                elif ctid == my_cid and clients[clid][2] == '0':
                    main.display_text_event.emit('<b>' + html.escape(clients[clid][0]) + '</b>' + ' has joined your channel')
                    if update_client_list() != 0:
                        print('ERROR [handle_data]: error updating client list while handling notifyclientmoved!')
                        continue
                elif clients[clid][1] == my_cid and ctid != my_cid:
                    main.display_text_event.emit('<b>' + html.escape(clients[clid][0]) + '</b> has left your channel to channel <b>' + html.escape(channels[ctid]) + '</b>')
                    if update_client_list() != 0:
                        print('ERROR [handle_data]: error updating client list while handling notifyclientmoved!')
                        continue
                elif clients[clid][2] == '0':
                    main.display_text_event.emit('<b>' + html.escape(clients[clid][0]) + '</b> has left your channel')
                    if update_client_list() != 0:
                        print('ERROR [handle_data]: error updating client list while handling notifyclientmoved!')
                        continue

            elif text.startswith('notifycliententerview '):
                ctid = get_param(text, 'ctid')
                clid = get_param(text, 'clid')

                if my_cid == '' or my_clid == '':
                    if whoami() != 0:
                        print('ERROR [handle_data]: error updating whoami while handling notifycliententerview!')
                        continue

                if clid not in clients.keys():
                    if update_client_list() != 0:
                        print('ERROR [handle_data]: error updating client list while handling notifycliententerview!')
                        continue

                if ctid == my_cid and clients[clid][2] == '0':
                    main.display_text_event.emit('<b>' + html.escape(clients[clid][0]) + '</b>' + ' has joined your channel')
                    if update_client_list() != 0:
                        print('ERROR [handle_data]: error updating client list while handling notifycliententerview!')
                        continue

            elif text.startswith('notifyclientleftview '):
                cfid = get_param(text, 'cfid')
                clid = get_param(text, 'clid')

                if (my_cid == '' or my_clid == ''):
                    if whoami() != 0:
                        print('ERROR [handle_data]: error updating whoami while handling notifyclientleftview!')
                        continue

                if clid not in clients.keys():
                    if update_client_list() != 0:
                        print('ERROR [handle_data]: error updating client list while handling notifyclientleftview!')
                        continue

                if cfid == my_cid and clients[clid][2] == '0':
                    main.display_text_event.emit('<b>' + html.escape(clients[clid][0]) + '</b>' + ' has left your channel')
                    clients[clid][1] = 'non-existant'

            elif text.startswith('notifyclientpoke '):
                name = ts_replace(get_param(text, 'invokername'))
                message = ts_replace(get_param(text, 'msg'))

                main.display_text_event.emit('<b> !!!POKE FROM ' + html.escape(name) + '!!! ' + html.escape(message) + '</b>')

            elif text.startswith('notifyclientupdated '):

                if ' client_nickname=' in text:
                    new_name = ts_replace(get_param(text, 'client_nickname'))
                    clid = ts_replace(get_param(text, 'clid'))
                    if clid in clients.keys() and clients[clid][2] == '0' and clients[clid][0] != new_name:
                        main.display_text_event.emit('<b>' + clients[clid][0] + '</b> is now known as <b>' + new_name + '</b>')

                if update_client_list() != 0:
                    print('ERROR [handle_data]: error updating client list while handling notifyclientupdated!')

            elif text.startswith('notifychanneledited '):
                if update_channel_list() != 0:
                    print('ERROR [handle_data]: error updating channel list while handling notifychanneledited!')

    def run(self):
        reconnect()

        if update_client_list() != 0:
            print('ERROR [TelnetThread.run]: error updating client list duirng initialization!')

        if update_channel_list() != 0:
            print('ERROR [TelnetThread.run]: error updating channel list duirng initialization!')

        if whoami() != 0:
            print('ERROR [TelnetThread.run]: error updating whoami duirng initialization!')

        while not self.breakflag:
            if data_queue:
                self.handle_data()

            try:
                raw_data = connection.read_until(b'\n\r').decode()
            except (OSError,EOFError):
                reconnect()
                continue

            while '\n\r' in raw_data:
                temp = raw_data.split('\n\r', 1)
                data_queue.append(temp[0])
                raw_data = temp[1]

        connection.close()

@pyqtSlot()
def append_speakers_text(text):
    if text + '\n' not in speakers_text:
        speakers_text.append(text + '\n')
        ui.textBrowser_speakers.setPlainText('')
        for t in speakers_text:
            ui.textBrowser_speakers.insertPlainText(t)

@pyqtSlot()
def remove_speakers_text(text):
    if text + '\n' in speakers_text:
        speakers_text.remove(text + '\n')
        ui.textBrowser_speakers.setPlainText('')
        for t in speakers_text:
            ui.textBrowser_speakers.insertPlainText(t)

@pyqtSlot()
def display_message(text):
    if debug:
        print('DEBUG [display_message]: text=' + text)

    ui.textBrowser_text_messages.append(text)

@pyqtSlot()
def text_message(name, text, mode):
    text = html.escape(text).replace('\n', '<br />')

    if mode == '3':
        name = '[SERVER] ' + name
    elif mode == '1':
        name = '[PM] ' + name

    #linkify text
    while '[URL]' and '[/URL]' in text:
        start_pos = text.find('[URL]')
        end_pos = text.find('[/URL]')
        url = text[start_pos + len('[URL]'):end_pos]

        text = (text[:start_pos] + r'<a href="' + url + r'">' + url + r'</a>' + text[end_pos + len('[/URL]'):])

    display_message('<b>' + html.escape(name) + '</b>' + ': ' + text)

@pyqtSlot()
def send_text_message():
    text = ui.lineEdit.text()
    ui.lineEdit.clear()

    #matches a lot of non-valid URIs but we're not the URI police so whatever
    text = re.sub(r'(?P<uri>(http|https|ftp):\/\/([^ ]+?\.[^ ]+?)+?)(?P<end> |$|\n)', r'[URL]\g<uri>[/URL]\g<end>',text)

    #reversed replace
    for fr, to in replace_list:
        text = text.replace(fr, to)

    send_text = 'sendtextmessage targetmode=2 msg=' + text
    if debug:
        print('DEBUG [send_text_message]: send_text=' + send_text)
    try:
        connection.write((send_text + '\n').encode('ascii'))
    except (OSError,EOFError):
        reconnect()
        connection.write((send_text + '\n').encode('ascii'))


def recieve_response():
    last = ''
    recieve_data = ''

    while not last.startswith('error '):
        try:
            last = connection.read_until(b'\n\r',1).decode()
            if debug:
                print("DEBUG [recieve_response]: " + last)
        except (OSError,EOFError):
            reconnect()
            last = connection.read_until(b'\n\r',1).decode()

        #this should only happen on timeout
        if last == '':
            print('ERROR [recieve_response]: did not recieve complete response! Recieved data may be unusable!')
            thread.breakflag = True
            return (None, None)

        #queue up any notifications ahead of the data we want
        notify_flag = False
        for item in notify_events:
            if last.startswith(item):
                data_queue.append(last)
                notify_flag = True
                break

        if not notify_flag:
            recieve_data += last

    e = (get_param(last, 'id'), get_param(last, 'msg'))

    if e[0] != '0':
        return ('', e)

    return (recieve_data, '')


def ts_replace(data):
    if debug:
        print('DEBUG [ts_place]: before=' + data)
    for to, fr in reversed(replace_list):
        if fr != r'\\':
            while re.search(r'([^\\]|^)'+re.escape(fr), data):
                data = re.sub(r'([^\\]|^)'+re.escape(fr), r'\1'+to, data)
        else:
            data = data.replace(fr, to)
    if debug:
        print('DEBUG [ts_place]: after=' + data)
    return data

def get_param(data,key):
    for value in data.split(' '):
        line = value.split('=', 1)
        if line[0] == key:
            return line[1].strip('\n\r')
    print(key + ' not found!!\nData: ' + data + ' \n')
    return None

def update_client_list():
    clients.clear()
    try:
        if debug:
            print('DEBUG [update_client_list]: sending clientlist command')
        connection.write('clientlist\n'.encode('ascii'))
    except (OSError,EOFError):
        reconnect()
        connection.write('clientlist\n'.encode('ascii'))

    data = recieve_response()
    if data == (None, None):
        return 1
    elif data[0] == '':
        print('ERROR [update_client_list]: id=' + data[1][0] + ' msg=' + ts_replace(data[1][1]))

    found = False

    for line in data[0].split('\n\r'):
        if 'clid' in line and 'client_nickname' in line and 'cid' in line:
            found = True
            for entry in line.split('|'):
                clid = get_param(entry, 'clid')
                cid = get_param(entry, 'cid')
                type = get_param(entry, 'client_type')

                name = ts_replace(get_param(entry, 'client_nickname'))

                if clid.isnumeric() and cid.isnumeric():
                    clients[clid] = [name, cid, type]
                else:
                    print('ERROR [update_client_list]: invalid entry: ' + entry)
                    return 1

    if not found:
        print('ERROR [update_client_list]: no valid data returned for clientlist')
        return 1
    return 0

def update_channel_list():
    global channels
    try:
        connection.write('channellist\n'.encode('ascii'))
    except (OSError,EOFError):
        reconnect()
        connection.write('channellist\n'.encode('ascii'))

    data = recieve_response()
    if data == (None, None):
        return 1
    elif data[0] == '':
        print('ERROR [update_channel_list]: id=' + data[1][0] + ' msg=' + ts_replace(data[1][1]))

    for line in data[0].split('\n\r'):
        if 'cid' in line and 'channel_name' in line:
            for entry in line.split('|'):
                cid = get_param(entry, 'cid')
                channel_name = ts_replace(get_param(entry, 'channel_name'))

                channels[cid] = channel_name
            return 0

    print('ERROR [update_channel_list]: no valid data returned for channellist')
    return 1


def whoami():
    global my_clid, my_cid

    try:
        connection.write('whoami\n'.encode('ascii'))
    except (OSError,EOFError):
        reconnect()
        connection.write('whoami\n'.encode('ascii'))

    data = recieve_response()
    if data == (None, None):
        return 1
    elif data[0] == '':
        print('ERROR [whoami]: id=' + data[1][0] + ' msg=' + ts_replace(data[1][1]))


    for line in data[0].split('\n\r'):
        if 'clid' in line and 'cid' in line:
            found = True
            my_clid = re.sub(r'[^0-9]', '', get_param(data[0], 'clid'))
            my_cid = re.sub(r'[^0-9]', '', get_param(data[0], 'cid'))
            return 0

    print('ERROR [whoami]: no valid data returned for whoami')
    return 1

def reconnect():
    try:
        connection.open(target_ip_addr,target_port,10)
        connection.read_until(b'selected schandlerid=1\n\r', 1)
        for event in notify_events:
            connection.write(('clientnotifyregister schandlerid=0 event=' + event + '\n').encode('ascii'))
            response = recieve_response()
            if response == (None,None):
                break
            elif response[0] == '':
                print('ERROR [reconnect]: id=' + response[1][0] + ' msg=' + response[1][1])
    except (OSError,EOFError):
        print('ERROR [reconnect]: cannot connect')
        thread.breakflag = True
        app.quit()

if __name__ == '__main__':
    thread = TelnetThread()

    app = QApplication(sys.argv)
    window = QMainWindow()
    ui = mainwindow.Ui_MainWindow()
    ui.setupUi(window)

    ui.textBrowser_text_messages.setOpenExternalLinks(True)

    window.show()
    main = Main()
    main.main()
