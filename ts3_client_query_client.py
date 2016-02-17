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

replace_dict = {
    '\\\\': '\\',
    '\\/': '/',
    '\\s': ' ',
    '\\p': '|',
    '\\a': '\a',
    '\\b': '\b',
    '\\f': '\f',
    '\\n': '\n',
    '\\r': '\r',
    '\\t': '\t',
    '\\v': '\v',
}

my_clid = ''
my_cid = ''

class Main(QObject):

    speakeron_event = pyqtSignal([str])
    speakeroff_event = pyqtSignal([str])
    display_text_event = pyqtSignal([str])
    text_message_event = pyqtSignal([str,str])

    def main(self):

        self.speakeron_event.connect(append_speakers_text)
        self.speakeroff_event.connect(remove_speakers_text)
        self.display_text_event.connect(display_message)
        self.text_message_event.connect(text_message)

        thread.start()

        ui.lineEdit.returnPressed.connect(send_text_message)

        app.exec_()
        thread.breakflag = True

class TelnetThread(QThread):

    breakflag = False

    @staticmethod
    def handle_data(data):

        for text in data:

            if text.startswith('notifytalkstatuschange '):
                clid = get_param(text, 'clid')

                if clid not in clients.keys():
                    update_client_list()

                if 'status=1' in text:
                    main.speakeron_event.emit(clients[clid][0])
                #handle case where connection is established while someone is speaking
                elif 'status=0' in text:
                    main.speakeroff_event.emit(clients[clid][0])

            elif text.startswith('notifytextmessage '):

                name = ts_replace(get_param(text, 'invokername'))
                message = ts_replace(get_param(text, 'msg'))

                main.text_message_event.emit(name, message)

            elif text.startswith('notifycurrentserverconnectionchanged '):
                update_client_list()
                update_channel_list()
                whoami()

            elif text.startswith('notifyclientmoved '):
                clid = get_param(text, 'clid')
                ctid = get_param(text, 'ctid')

                if my_cid == '':
                    whoami()

                if clid not in clients.keys():
                    update_client_list()

                if ctid not in channels.keys():
                    update_channel_list()

                if ctid == my_cid:
                    main.display_text_event.emit(clients[clid][0] + ' has joined your channel')
                elif clients[clid][1] == my_cid and ctid != my_cid:
                    main.display_text_event.emit(clients[clid][0] + ' has left your channel to channel <b>' + channels[ctid] + '</b>')

            elif text.startswith('notifycliententerview '):
                ctid = get_param(text, 'ctid')
                clid = get_param(text, 'clid')

                if my_cid == '':
                    whoami()

                if clid not in clients.keys():
                    update_client_list()

                if ctid == my_cid:
                    main.display_text_event.emit(clients[clid][0] + ' has joined your channel')

            elif text.startswith('notifyclientleftview '):
                cfid = get_param(text, 'cfid')
                clid = get_param(text, 'clid')

                if my_cid == '':
                    whoami()

                if clid not in clients.keys():
                    update_client_list()

                if cfid == my_cid:
                    main.display_text_event.emit(clients[clid][0] + ' has left your channel')

            elif text.startswith('notifyclientpoke '):
                name = ts_replace(get_param(text, 'invokername'))
                message = ts_replace(get_param(text, 'msg'))

                main.display_text_event.emit('<b> !!POKE FROM ' + name + '!!! ' + message + '</b>')

            elif text.startswith('notifyclientupdated '):
                update_client_list()

            elif text.startswith('notifychanneledited '):
                update_channel_list()

    def run(self):

        reconnect()

        update_client_list()
        update_channel_list()
        whoami()

        while not self.breakflag:
            data = []
            try:
                raw_data = connection.read_until(b'\n\r').decode()
            except (OSError,EOFError):
                reconnect()
                continue

            while '\n\r' in raw_data:
                temp = raw_data.split('\n\r', 1)
                data.append(temp[0])
                raw_data = temp[1]

            self.handle_data(data)

        connection.close()

def ts_replace(data):
    for fr, to in replace_dict.items():
        data = data.replace(fr, to)
    return data

def get_param(data,key):
    temp = data.split(' ')
    for value in temp:
        line = value.split('=', 1)
        if line[0] == key:
            return line[1]
    print(key + ' not found!!\nData: ' + data + ' \n')
    return None

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
    ui.textBrowser_text_messages.append(text)

@pyqtSlot()
def text_message(name, text):
    #linkifying text leads to a bug i've been unable to reliably reproduce much less fix wherein regular text after
    #   a URL will also be considered part of the link
    #   i just gave up after two months

    text = ts_replace(text)
    name = ts_replace(name)

    if '[URL]' and '[/URL]' in text:
        text = re.sub(r'\[/?URL\]', '', text)

    display_message(name + ': ' + text)

@pyqtSlot()
def send_text_message(text='',retry=0):
    if retry > 1:
        display_message('ERROR: cannot connect')
        thread.breakflag = True
        return
    if text == '':
        text = ui.lineEdit.text()
    ui.lineEdit.clear()

    #reverse replace
    for to, fr in replace_dict:
        text.replace(fr, to)

    send_text = 'sendtextmessage targetmode=2 msg=' + text
    try:
        connection.write((send_text + '\n').encode('ascii'))
    except (OSError,EOFError):
        reconnect()
        send_text_message(send_text, retry + 1)

def update_client_list():
    try:
        connection.write('clientlist\n'.encode('ascii'))
    except (OSError,EOFError):
        reconnect()
        connection.write('clientlist\n'.encode('ascii'))

    try:
        data = connection.read_until(b'\n\r').decode()
    except (OSError,EOFError):
        reconnect()
        data = connection.read_until(b'\n\r').decode()

    for line in data.split('\n\r'):
        if 'clid' in line and 'client_nickname' in line and 'cid' in line:
            for entry in line.split('|'):
                clid = get_param(entry, 'clid')
                cid = get_param(entry, 'cid')

                name = ts_replace(get_param(entry, 'client_nickname'))

                clients[clid] = (name, cid)

def update_channel_list():
    try:
        connection.write('channellist\n'.encode('ascii'))
    except (OSError,EOFError):
        reconnect()
        connection.write('channellist\n'.encode('ascii'))

    try:
        data = connection.read_until(b'\n\r').decode()
    except (OSError,EOFError):
        reconnect()
        data = connection.read_until(b'\n\r').decode()

    for line in data.split('\n\r'):
        if 'cid' in line and 'channel_name' in line:
            for entry in data.split('|'):
                cid = get_param(entry, 'cid')
                channel_name = ts_replace(get_param(entry, 'channel_name'))

                channels[cid] = channel_name

def whoami():
    global my_clid, my_cid

    try:
        connection.write('whoami\n'.encode('ascii'))
    except (OSError,EOFError):
        reconnect()
        connection.write('whoami\n'.encode('ascii'))

    try:
        data = connection.read_until(b'\n\r').decode()
    except (OSError,EOFError):
        reconnect()
        data = connection.read_until(b'\n\r').decode()

    for line in data.split('\n\r'):
        if 'clid' in line and 'cid' in line:
            my_clid = re.sub(r'[^0-9]', '', get_param(data, 'clid'))
            my_cid = re.sub(r'[^0-9]', '', get_param(data, 'cid'))

def reconnect():
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
    try:
        connection.open(target_ip_addr,target_port,10)
        connection.read_until(b'selected schandlerid=1\n\r', 1)
        for event in notify_events:
            connection.write(('clientnotifyregister schandlerid=0 event=' + event + '\n').encode('ascii'))
    except OSError:
        display_message('ERROR: cannot connect')
        thread.breakflag = True

if __name__ == '__main__':
    thread = TelnetThread()

    app = QApplication(sys.argv)
    window = QMainWindow()
    ui = mainwindow.Ui_MainWindow()
    ui.setupUi(window)

    window.show()
    main = Main()
    main.main()
