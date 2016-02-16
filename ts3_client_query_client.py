import re
import sys
import telnetlib

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QThread
from PyQt5.QtWidgets import QApplication, QMainWindow

import mainwindow

clients = {}
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

        text = data.strip('\n\r')

        if text.startswith('notifytalkstatuschange'):
            clid_pos = text.find('clid=')
            clid = text[clid_pos+len('clid='):text.find(' ',clid_pos)]

            if clid not in clients.keys():
                update_client_list()

            if 'status=1' in text:
                main.speakeron_event.emit(clients[clid])
            #handle case where connection is established while someone is speaking
            elif 'status=0' in text:
                main.speakeroff_event.emit(clients[clid])

        elif text.startswith('notifytextmessage'):

            name_pos = text.find('invokername=')+len('invokername=')
            name = text[name_pos:text.find(' ',name_pos)]

            message_pos = text.find('msg=')+len('msg=')
            message = text[message_pos:text.find(' ',message_pos)]
            main.text_message_event.emit(name, message)

        elif text.startswith('notifycurrentserverconnectionchanged'):
            update_client_list()

    def run(self):

        reconnect()

        update_client_list()

        while not self.breakflag:
            try:
                data = connection.read_until(b'\n\r').decode()
            except (OSError,EOFError):
                reconnect()
                continue
            self.handle_data(data)

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
    ui.textBrowser_text_messages.append(text)

@pyqtSlot()
def text_message(name, text):
    #linkifying text leads to a bug i've been unable to reliably reproduce much less fix wherein regular text after
    #   a URL will also be considered part of the link
    #   i just gave up after two months

    for fr, to in replace_dict:
        text = text.replace(fr, to)
        name = name.replace(fr, to)

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

    while 'clid' not in data:
        try:
            data = connection.read_until(b'\n\r').decode()
        except (OSError,EOFError):
            reconnect()

    for entry in data.split('|'):
        key = entry[5:entry.find(' ')]
        name_pos = entry.find('client_nickname=')+len('client_nickname=')
        name = entry[name_pos:entry.find(' ',name_pos)]

        for fr, to in replace_dict:
            name = name.replace(fr, to)

        clients[key] = name

def reconnect():
    notify_events = ['notifytalkstatuschange','notifytextmessage','notifycurrentserverconnectionchanged']
    try:
        connection.open(target_ip_addr,target_port,10)
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
