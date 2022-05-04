######## This is the server file that manages the communication for multiplayer modes
######## Run this file before you run the game "__init__.py"

import socket
import threading
from queue import Queue
import rsa
import base64
import json
import os
import random
from email.mime.text import MIMEText
from email.header import Header
import smtplib

HOST = socket.gethostbyname(socket.gethostname())  # getting IP address
BACKLOG = 2
print("\nYour IP address is:\n" + HOST + "\n")

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((HOST, 0))  # letting the computer select an available port
server.listen(BACKLOG)
print("Your PORT number is:\n" + str(server.getsockname()[1]) + "\n")
print("Looking for connection...")


def send_email(to_addr):
    # source email address
	#from_addr = "2931318857@qq.com"
    from_addr = "pidoudfo@gmail.com"
    # smtp password
    password = "Arialiu0822.."
    # smtp server address
    smtp_server = "smtp.gmail.com"
    # smtp server port
    smtp_port = 465

    code = str(random.randint(100000,999999))
    msg = MIMEText('<html><body><h3>Hello! Your verification code is %s.</h3></body></html>' % code, 'html', 'utf-8')
    msg['Subject'] = Header('Your Verification Code', 'utf-8').encode('utf-8')
    
    server = smtplib.SMTP_SSL(smtp_server, smtp_port)
    server.login(from_addr, password)
    server.sendmail(from_addr, [to_addr], msg.as_string())
    server.quit()
    return code

class User(object):
    '''
    Record the user's email, password and verification code, stored on disk.
    '''
    FILENAME = "users.json"
    _users = {}

    def __init__(self,email = "",password = "",verif_code = "") -> None:
        super().__init__()
        self.email = email
        self.password = password
        self.verif_code = verif_code
        
    @classmethod
    def _load_users(cls):
        with open(cls.FILENAME, 'r') as f:
            cls._users = json.load(f)
        for k in cls._users:
            cls._users[k] = cls(**(cls._users[k]))

    @classmethod
    def _save_users(cls):
        with open(cls.FILENAME, 'w') as f:
            json.dump(cls._users, f, default = lambda obj: obj.__dict__)

    @classmethod
    def load_user(cls, email):
        cls._load_users()
        return cls._users.get(email, None)

    def save(self):
        User._users[self.email] = self
        User._save_users()

if not os.path.isfile(User.FILENAME):
    with open(User.FILENAME, 'w') as f:
        json.dump({}, f)
#################################################################
# Sockets server code copied from 15-112 Sockets mini-lecture


class ClientInfo(object):
    def __init__(self) -> None:
        super().__init__()
        self.pubkey = None
        self.cID = None
        self.client_sock = None

def handleClient(client, serverChannel, cID, clients):
    client.setblocking(1)
    msg = ""
    while True:
        try:
            msg += client.recv(10).decode("UTF-8")
            command = msg.split("\n")
            while len(command) > 1:
                readyMsg = command[0]
                
                readyMsg = base64.b64decode(readyMsg)
                readyMsg = rsa.decrypt(readyMsg, privkey)
                readyMsg = readyMsg.decode("UTF-8")

                serverChannel.put(str(cID) + " " + readyMsg.strip())
                msg = "\n".join(command[1:])
                command = msg.split("\n")
        except Exception as err:
            # we failed
            print(err)
            return

def serverThread(clients, serverChannel):
    while True:
        msg = serverChannel.get(True, None)
        print("msg recv: ", msg)
        msgList = msg.split(" ")
        senderID = msgList[0]
        instruction = msgList[1]
        details = " ".join(msgList[2:])
        if details != "":
            for cID in clients:
                if cID != senderID:
                    sendMsg = instruction + " " + senderID + " " + details + "\n"

                    encodeMsg = rsa.encrypt(sendMsg.encode("UTF-8"), clients[cID].pubkey)
                    encodeMsg = base64.b64encode(encodeMsg)
                    clients[cID].client_sock.send((encodeMsg.decode("UTF-8") + "\n").encode("UTF-8"))

                    print("> sent to %s:" % cID, sendMsg[:-1])
        print()
        serverChannel.task_done()

def handleLoadIn(client: socket.socket):
    client.setblocking(1)
    while True:
        # get email and password
        msg = ""
        command = []
        is_ok = True
        user = None
        while True:
            msg += client.recv(1024).decode("UTF-8")
            if '\n' in msg:
                command = msg.split('\n')[0]
                command = command.split(" ")
                load_type = command[0]
                email = command[1]
                password = command[2]

                if load_type == 'signin':
                    user = User.load_user(email)
                    if user and user.password == password:
                        user.verif_code = send_email(email)
                        client.send("mailsent\n".encode("UTF-8"))
                    else:
                        client.send("error\n".encode("UTF-8"))
                        is_ok = False
                else: # sign up
                    if User.load_user(email) is not None:
                        client.send("error\n".encode("UTF-8"))
                        is_ok = False
                    else:
                        code = send_email(email)
                        user = User(email, password, code)
                        client.send("mailsent\n".encode("UTF-8"))
                break

        if not is_ok:
            # restart sign in or sign up
            continue
        
        # check email code
        msg = ""
        command = []
        is_ok = True
        while True:
            msg += client.recv(1024).decode("UTF-8")
            if '\n' in msg:
                command = msg.split('\n')[0]
                code = command

                if code == user.verif_code:
                    client.send("ok\n".encode("UTF-8"))
                    user.save()
                else:
                    client.send("error\n".encode("UTF-8"))
                    is_ok = False

                break

        if is_ok:
            break


# clientele = dict()
clients = {}
playerNum = 0

serverChannel = Queue(100)
threading.Thread(target=serverThread, args=(clients, serverChannel)).start()

names = ["PlayerA", "PlayerB"]


(pubkey, privkey) = rsa.newkeys(1024)

while True:
    client, address = server.accept()

    handleLoadIn(client)

    client_info = ClientInfo()
    # myID is the key to the client in the clientele dictionary
    myID = names[playerNum]
    print(myID, playerNum)

    client_info.cID = myID
    client_info.client_sock = client

    # send server's public key
    client.send(("pubkey %s\n" % pubkey).encode("UTF-8"))

    # receive client's public key
    client.setblocking(1)
    msg = ""
    while True:
        msg += client.recv(1024).decode("UTF-8")
        command = msg.split("\n")
        if len(command) > 1:
            content = command[0]
            if content.startswith("pubkey"):
                pubkey_str = content[content.find(" ") + 1 :]
                n_e = pubkey_str[
                    pubkey_str.find("(") + 1 : pubkey_str.find(")")
                ].split(",")
                n = int(n_e[0].strip())
                e = int(n_e[1].strip())
                client_info.pubkey = rsa.PublicKey(n, e)
                break
            msg = ""


    for cID in clients:
        print(cID, repr(playerNum))

        sendMsg = "newPlayer %s\n" % myID
        encodeMsg = rsa.encrypt(sendMsg.encode("UTF-8"), clients[cID].pubkey)
        encodeMsg = base64.b64encode(encodeMsg)
        clients[cID].client_sock.send((encodeMsg.decode("UTF-8") + "\n").encode("UTF-8"))

        sendMsg = "newPlayer %s\n" % cID
        encodeMsg = rsa.encrypt(sendMsg.encode("UTF-8"), client_info.pubkey)
        encodeMsg = base64.b64encode(encodeMsg)
        client.send((encodeMsg.decode("UTF-8") + "\n").encode("UTF-8"))

    clients[myID] = client_info

    sendMsg = "myIDis %s\n" % myID
    encodeMsg = rsa.encrypt(sendMsg.encode("UTF-8"), client_info.pubkey)
    encodeMsg = base64.b64encode(encodeMsg)
    client.send((encodeMsg.decode("UTF-8") + "\n").encode("UTF-8"))

    print("connection recieved from %s" % myID)
    threading.Thread(
        target=handleClient, args=(client, serverChannel, myID, clients)
    ).start()
    playerNum += 1

    
