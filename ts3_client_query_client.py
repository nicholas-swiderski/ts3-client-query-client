import sys
import telnetlib
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QThread
import mainwindow

clients = {}
speakers_text = []
text_messages_text = []
send_text_messages_queue = []
connection = telnetlib.Telnet()
target_ip_addr = '192.168.1.2'
target_port = 25639

class Main(QObject):

    speakeron_event = pyqtSignal([str])
    speakeroff_event = pyqtSignal([str])
    text_event = pyqtSignal([str,str])
    add_client_event = pyqtSignal([str,str])

    def main(self):

        self.speakeron_event.connect(append_speakers_text)
        self.speakeroff_event.connect(remove_speakers_text)
        self.text_event.connect(text_message)
        self.add_client_event.connect(add_client)

        thread.start()

        ui.lineEdit.returnPressed.connect(send_text_message)

        app.exec_()
        thread.breakflag = True

class TelnetThread(QThread):

    breakflag = False

    @staticmethod
    def handle_data(data):

        text = data.strip('\n\r')

        if text.startswith('notifytalkstatuschange '):
            clid_pos = text.find('clid=')
            clid = text[clid_pos+len('clid='):]
            if 'status=1' in text:
                main.speakeron_event.emit(clients[clid])
            # handle case where connection is established while someone is speaking
            elif 'status=0' in text and clid in clients.keys():
                main.speakeroff_event.emit(clients[clid])

        elif text.startswith('notifytextmessage '):

            name_pos = text.find('invokername=')+len('invokername=')
            name = text[name_pos:text.find(' ',name_pos)].replace('\s',' ')

            message_pos = text.find('msg=')+len('msg=')
            message = text[message_pos:text.find(' ',message_pos)].replace('\s',' ')

            main.text_event.emit(name, message)

        elif text.startswith('notifycliententerview '):
            clid_pos = text.find('clid=')
            clid = text[clid_pos+len('clid='):text.find(' ',clid_pos)]
            client_nickname_pos = text.find('client_nickname=')
            client_nickname = text[client_nickname_pos+len('client_nickname='):text.find(' ',client_nickname_pos)].replace('\s',' ')
            main.add_client_event.emit(clid,client_nickname)
            main.text_event.emit(client_nickname + ' has joined')

        elif text.startswith('notifyclientleftview '):
            clid_pos = text.find('clid=')
            clid = text[clid_pos+len('clid='):]
            print('CLID ',clid)
            main.text_event.emit(clients[clid] + ' has left')

    def run(self):

        try:
            connection.open(target_ip_addr,target_port,10)
        except OSError:
            main.text_event.emit("ERROR: cannot connect")
            return

        try:
            connection.write("clientlist\n".encode('ascii'))
        except (OSError,EOFError):
            reconnect()
            connection.write("clientlist\n".encode('ascii'))

        try:
            data = connection.read_until(b"\n\r").decode('ascii')
        except (OSError,EOFError):
            reconnect()
            data = connection.read_until(b"\n\r").decode('ascii')

        while 'clid' not in data:
            try:
                data = connection.read_until(b"\n\r").decode('ascii')
            except (OSError,EOFError):
                reconnect()

        for entry in data.split('|'):
            key = entry[5:entry.find(' ')]
            name_pos = entry.find('client_nickname=')+len('client_nickname=')
            name = entry[name_pos:entry.find(' ',name_pos)].replace('\s',' ')

            clients[key] = name

        try:
            connection.write("clientnotifyregister schandlerid=0 event=any\n".encode('ascii'))
        except (OSError,EOFError):
            reconnect()
            connection.write("clientnotifyregister schandlerid=0 event=any\n".encode('ascii'))

        while not self.breakflag:
            try:
                data = connection.read_until(b"\n\r").decode('ascii')
            except (OSError,EOFError):
                reconnect()
                continue
            self.handle_data(data)

        connection.close()

@pyqtSlot()
def append_speakers_text(text):
    speakers_text.append(text + "\n")
    ui.textBrowser_speakers.setPlainText('')
    for t in speakers_text:
        ui.textBrowser_speakers.insertPlainText(t)

@pyqtSlot()
def remove_speakers_text(text):
    if text + "\n" in speakers_text:
        speakers_text.remove(text + "\n")
        ui.textBrowser_speakers.setPlainText('')
        for t in speakers_text:
            ui.textBrowser_speakers.insertPlainText(t)

@pyqtSlot()
def text_message(name,text):
    if '[URL]' in text and '[\/URL]' in text:
        while '[URL]' in text:
            tag_start_pos = text.find('[URL]')
            tag_end_pos = text.find('[\/URL]')
            url = text[tag_start_pos+len('[URL]'):tag_end_pos].replace('\/','/')
            text = text[:tag_start_pos] + '<a href="' + url + '">' + url + '</a>' + text[tag_end_pos+len('[\/URL]'):]

    ui.textBrowser_text_messages.append(name + ': ' + text)

@pyqtSlot()
def send_text_message(text='',retry=0):
    if retry > 1:
        text_message("ERROR: cannot connect")
        thread.breakflag = True
        return
    if text == '':
        text = ui.lineEdit.text()
    ui.lineEdit.clear()
    send_text = 'sendtextmessage targetmode=2 msg=' + text.replace(' ','\s')
    try:
        connection.write((send_text + "\n").encode('ascii'))
    except (OSError,EOFError):
        reconnect()
        send_text_message(send_text,1)


@pyqtSlot(str,str)
def add_client(clid,name):
    clients[clid] = name

def reconnect():
    try:
        connection.open(target_ip_addr,target_port,10)
        connection.write("clientnotifyregister schandlerid=0 event=any\n".encode('ascii'))
    except OSError:
        text_message("ERROR: cannot connect")
        thread.breakflag = True

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
