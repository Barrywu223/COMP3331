'''
Server for COMP3331 Assignment
Written by Barry Wu, z5207984
'''
from socket import *
from threading import Thread
import json
import time
from datetime import datetime
import sys, select

# ============================================================================================================
# Global values
existing_users = []
active_users = []
rooms = {
    'room': []
}
blocked_users = {}
failed_attempts = 0
# ============================================================================================================

"""
    Multi-Thread Class adapted from Wei Song's code
"""
class ServerThread(Thread):
    def __init__(self, clientAddress, clientSocket):
        Thread.__init__(self)
        self.clientAddress = clientAddress
        self.clientSocket = clientSocket
        self.clientAlive = False
        self.loginAttempts = 0
        self.udp_port = 0
        self.username = ''
        print("===== New connection created for: ", clientAddress)
        self.clientAlive = True

    # ========================================================================================================
    def run(self):
        message = ''
        while self.clientAlive:
            # use recv() to receive message from the client
            data = self.clientSocket.recv(1024)
            message = json.loads(data.decode('utf-8'))
            # handle message from the client
            if message['message_type'] == 'login':
                print("[recv] New login request")
                self.process_login(message['username'], message['password'])
            elif message['message_type'] == 'udp':
                print("[recv] Receiving UDP port of client")
                self.add_to_logged_users(self.username, message['port'])
            elif message['message_type'] == 'logout':
                print("[recv] Logout request")
                self.logout(message['username'])
                self.clientAlive = False
            elif message['message_type'] == 'BCM':
                print("[recv] Broadcast message request")
                self.bcm(message['message'], message['username'])
            elif message['message_type'] == 'ATU':
                print("[recv] Active users request")
                self.atu()
            elif message['message_type'] == 'SRB':
                print("[recv] Create room request")
                self.srb(message['owner'], message['usernames'])
            elif message['message_type'] == 'SRM':
                print("[recv] Send room message request")
                self.srm(message['room_id'], message['message'])
            elif message['message_type'] == 'RDM':
                print("[recv] Read message request")
                self.rdm(message['type'], message['timestamp'])
            elif message['message_type'] == 'UDP':
                print("[recv] Upload file request")
                self.udp(message['audience'])
            else:
                print("[recv] " + message['message_type'])
                print("[send] Cannot understand this message")
                message = 'Cannot understand this message'
                self.clientSocket.send(message.encode())
            print("================================")
    
    # ========================================================================================================
    def process_login(self, username, password):
        # Check if user is currently blocked
        global blocked_users
        if username in blocked_users:
            if int(time.time()) - blocked_users.get(username) < 10:
                message = 'BLOCK'
                print('[send] ' + message)
                self.clientSocket.send(message.encode())
                self.clientAlive = False
                return
            else:
                blocked_users.pop(username)

        # Check credentials.txt if the username + password is valid
        credentials = f"{username} {password}"
        file = open("credentials.txt", 'r')
        lines = file.read()
        for line in lines.split('\n'):
            if line == credentials:    
                message = 'OK'
                print('[send] ' + message)
                self.clientSocket.send(message.encode())
                self.username = username
                return

        # Incorrect username/password - check to block or allow user to try again
        self.loginAttempts += 1
        if self.loginAttempts >= failed_attempts:
            message = 'BLOCK'
            blocked_users.update({f'{username}': int(time.time())})
            self.clientAlive = False
        else:
            message = 'INVALID'
        print('[send] ' + message)
        self.clientSocket.send(message.encode())
    
    # ========================================================================================================
    def add_to_logged_users(self, username, udp_port):
        # Add username to existing users unless already there
        if username not in existing_users:
            existing_users.append(username)

        # Add username to active users
        active_users.append(username)

        # Create user data to add to userlog
        now = datetime.now()
        timestamp = now.strftime("%d %b %Y %H:%M:%S")
        file = open("userlog.txt", 'r+')
        user_num = len(file.readlines()) + 1
        log = f"{user_num}; {timestamp}; {username}; {self.clientAddress[0]}; {udp_port}"
        file.write(f"{log}\n")
        file.close()

    # ========================================================================================================
    def logout(self, username):
        # Remove username from active_users list
        active_users.remove(username)
        
        # Remove user data from userlog and truncate file
        with open("userlog.txt", "r+") as file:
            lines = file.readlines()
            file.seek(0)
            for line in lines:
                if username not in line:
                    file.write(line)
            file.truncate()
        print(f"{username} logged out")
        message = "OK"
        self.clientSocket.send(message.encode())
    
    # ========================================================================================================
    def bcm(self, message, username):
        # Add message details to messagelog
        file = open("messagelog.txt", 'r+')
        message_num = len(file.readlines()) + 1
        now = datetime.now()
        timestamp = now.strftime("%d %b %Y %H:%M:%S")
        log = f"{message_num}; {timestamp}; {username}; {message}"
        file.write(f"{log}\n")
        file.close()
        client_response = f"Broadcast message, #{message_num}; {timestamp}"
        print(f"Broadcast message from {username} sent: {message}")
        self.clientSocket.send(client_response.encode())
    
    # ========================================================================================================
    def atu(self):
        # Search for active users other than client
        file = open("userlog.txt", 'r')
        lines = file.readlines()
        message = ''
        for line in lines:
            if self.username not in line:   
                message += line
        if message == '':
            message = "No other active user"
        print("Active user request completed")
        self.clientSocket.send(message.encode())
    
    # ========================================================================================================
    def srb(self, owner, usernames):
        members = [owner] + usernames
        # if all users all already in a room
        for room in rooms['room']:
            if all(users in room['members'] for users in members):
                message = f"A separate room (ID: {room['room_id']}) already created for these users"
                self.clientSocket.send(message.encode())
                print("Error - all users requested already in an existing room")
                return

        # if all users exist and are online
        if all(users in active_users for users in usernames):
            room_id = len(rooms['room'])
            room = {
                'room_id': room_id,
                'members': members
            }
            rooms['room'].append(room)
            file = open(f"SR_{room_id}_messagelog.txt", 'w')
            file.close()
            message = f"Separate chat room has been created, room ID: {room_id}\nUsers in this room: " + ', '.join(members)
            print(f"Room {room_id} successfully created")
        
        # if a user does not exist
        elif not all(users in existing_users for users in usernames):
            invalid_member = ', '.join([x for x in usernames if x not in existing_users])
            message = invalid_member + " does not exist"
            print("Error - user(s) requested does not exist")
        
        # if a user is offline
        else:
            offline_member = ', '.join([x for x in usernames if x not in active_users])
            message = offline_member + " is offline"
            print("Error - user(s) are offline")
            
        self.clientSocket.send(message.encode())

    # ========================================================================================================    
    def srm(self, room_id, message):
        # Get room by room_id
        room = get_room(room_id)

        # If room is invalid
        if room is None:
            message = "The separate room does not exist"
            self.clientSocket.send(message.encode())
            print(f"Error - room {room_id} does not exist")
            return
        
        # If client is not a member of room
        if self.username not in room['members']:
            message = "You are not in this separate room chat"
            self.clientSocket.send(message.encode())
            print(f"Error - client is not a member of room {room_id}")
            return
        
        # Add message to room's messagelog
        file = open(f"SR_{room_id}_messagelog.txt", 'r+')
        message_num = len(file.readlines()) + 1
        now = datetime.now()
        timestamp = now.strftime("%d %b %Y %H:%M:%S")
        log = f"{message_num}; {timestamp}; {self.username}; {message}"
        file.write(log)
        message = f"SRM #{message_num}, {timestamp}"
        self.clientSocket.send(message.encode())
        print(f"Succesfully message room {room_id}")
                
    # ========================================================================================================
    def rdm(self, message_type, timestamp):
        # Check if message type is broadcast message
        message = ''
        if message_type == 'b':
            with open("messagelog.txt", 'r') as file:
                lines = file.readlines()
                message += get_messages_after_timestamp(lines, timestamp)
        # Otherwise it's a room message
        else:
            user_rooms = []
            for room in rooms['room']:
                if self.username in room['members']:
                    user_rooms.append(room['room_id'])
            for id in user_rooms:
                with open(f"SR_{id}_messagelog.txt", 'r') as file:
                    lines = file.readlines()
                    message += get_messages_after_timestamp(lines, timestamp)
        if message == '':
            message = "No new messages"
        self.clientSocket.send(message.encode())
        print("Messages requested by client successfully sent")
    
    # ========================================================================================================
    def udp(self, audience):
        # Check if audience user exists
        if audience not in existing_users:
            message = {'response': "INVALID", 'message': f"{audience} does not exist"}
            self.clientSocket.send(bytes(json.dumps(message),encoding='utf-8'))
            print("Error - requested user does not exist")
            return
        # Check if audience user is active
        elif audience not in active_users:
            message = {'response': "INACTIVE", 'message': f"{audience} is offline"}
            self.clientSocket.send(bytes(json.dumps(message),encoding='utf-8'))
            print("Error - request user is offline")
            return
        # Open user log and send address + port
        client_address = ''
        with open("userlog.txt", 'r') as file:
            lines = file.readlines()
            for line in lines:
                if audience in line:
                    line_list = line.split()
                    client_address = line_list[6:]
        message = {'response': "OK", 'message': client_address}
        self.clientSocket.send(bytes(json.dumps(message),encoding='utf-8'))
        print("Address and port of requested UDP client succesfully sent")

# ============================================================================================================
# Helper functions

# Gets room details if exists, else return None
def get_room(room_id):
    for room in rooms['room']:
        if room['room_id'] == room_id:
            return room
    return None

# Returns all messages after a timestamp, else return empty string
def get_messages_after_timestamp(lines, timestamp):
    message = ''
    for line in lines:
        line_list = line.split()
        msg_timestamp = ' '.join(line_list[1:5])
        if (datetime.strptime(msg_timestamp, "%d %b %Y %H:%M:%S;")  > datetime.strptime(timestamp, "%d %b %Y %H:%M:%S")):
            message += ''.join(line_list[5][:-1]) + ': '
            message += ' '.join(line_list[6:]) + '\n'
    return message
        
# ============================================================================================================
def start_server(port):
    # define socket for the server side and bind address
    serverSocket = socket(AF_INET, SOCK_STREAM)
    serverAddress = ('', port)
    serverSocket.bind(serverAddress)

    # create log files
    f = open('userlog.txt', 'w')
    f.close()
    f = open('messagelog.txt', 'w')
    f.close()

    while True:
        serverSocket.listen()
        clientSockt, clientAddress = serverSocket.accept()
        print("Connected to ", clientAddress[0], " ", clientAddress[1])
        clientThread = ServerThread(clientAddress, clientSockt)
        clientThread.start()

# ============================================================================================================
def set_failed_attempts(attempts):
    global failed_attempts
    failed_attempts = attempts
    return

# ============================================================================================================
if __name__ == '__main__':
    # acquire server host, port and no. of allowed failed attempts from command line parameter
    if len(sys.argv) != 3:
        print("\n===== Error usage, python3 TCPServer3.py SERVER_PORT No. of failed attempts======\n")
        exit(0)
    serverPort = int(sys.argv[1])
    attempts = int(sys.argv[2])

    # Check if no. of failed attempts is valid
    if (attempts > 5 or attempts < 1):
        print(f"Invalid number of allowed failed consecutive attempts: {attempts}. The valid value of failed attempts should be between 0 and 6")
        exit(0)
    set_failed_attempts(attempts)

    print("\n===== Server is running =====")
    print("===== Waiting for connection request from clients...=====")
    start_server(serverPort)