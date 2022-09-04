'''
Client for COMP3331 Assignment
Written by Barry Wu, z5207984
'''
from socket import *
import json
import sys
import time
from threading import Thread
from datetime import datetime

# ============================================================================================================
# Global variables
clientname = ''
udp_port = 0

# ============================================================================================================
# Client UDP threads
def send_file(udpSocket, presenter, filename, clientAddress, clientPort):
    print(f"sending file {filename}")
    with open(filename, 'rb') as file:
        data = file.read()
    new_filename = presenter + '_' + filename
    udpSocket.sendto(len(new_filename).to_bytes(8, 'big'), (clientAddress, clientPort))
    udpSocket.sendto(new_filename.encode('utf-8'), (clientAddress, clientPort))
    udpSocket.sendto(len(data).to_bytes(8, 'big'), (clientAddress, clientPort))
    with open(filename, 'rb') as file:
        data = file.read(10000)
        while data:
            udpSocket.sendto(data, (clientAddress, clientPort))
            time.sleep(0.01)
            data = file.read(10000)
    udpSocket.sendto(data, (clientAddress, clientPort))

# Client UDP server
def recv_file(udpSocket):
    while True:
        filename_size = b""
        while len(filename_size) < 8:
            size = udpSocket.recv(8 - len(filename_size))
            filename_size += size
        filename_size = int.from_bytes(filename_size, 'big')
        filename = b""
        while len(filename) < filename_size:
            buffer = udpSocket.recv(filename_size - len(filename))
            filename += buffer
        filename = filename.decode('utf-8')
        presenter = filename.split('_')[0]
        expected_size = b""
        while len(expected_size) < 8:
            size = udpSocket.recv(8 - len(expected_size))
            expected_size += size
        expected_size = int.from_bytes(expected_size, 'big')
        packet = b""
        while len(packet) < expected_size:
            buffer = udpSocket.recv(expected_size - len(packet))
            packet += buffer
        with open(filename, 'wb') as file:
            file.write(packet)
        print(f"\nA file has been received from {presenter}")
        print("Enter one of the following commands (BCM, ATU, SRB, SRM, RDM, OUT, UDP): ")
# ============================================================================================================

# ============================================================================================================
# Handles initial login request
def send_login_info(clientSocket, udp_port):
    username = input("Username: ")
    while True:
        password = input("Password: ")
        message = {
            'message_type': 'login',
            'username': username,
            'password': password
        }
        clientSocket.send(bytes(json.dumps(message),encoding='utf-8'))
        # receive response from the server
        # 1024 is a suggested packet size, you can specify it as 2048 or others
        data = clientSocket.recv(1024)
        receivedMessage = data.decode()
        if receivedMessage == "OK":
            global clientname
            clientname = username
            message = {'message_type': 'udp', 'port': f"{udp_port}"}
            clientSocket.send(bytes(json.dumps(message),encoding='utf-8'))
            break
        elif receivedMessage == "INVALID":
            print("Invalid credentials. Please try again")
            continue

        elif receivedMessage == "BLOCK":
            print("Your account is blocked due to multiple login failures. Please try again later")
            exit()

# ============================================================================================================
def logout(udpSocket, clientSocket):
    message = {'message_type': 'logout', 'username': clientname}
    clientSocket.send(bytes(json.dumps(message),encoding='utf-8'))
    data = clientSocket.recv(1024)
    if data.decode() == "OK":
        print(f"See you next time {clientname}")
        clientSocket.close()
        udpSocket.close()
        exit()
    else:
        print("Logout failed")

# ============================================================================================================
def broadcast_message(message):
    command = {'message_type': 'BCM', 'message': message, 'username': clientname}
    return command

# ============================================================================================================
def download_active_users():
    command = {'message_type': 'ATU'}
    return command

# ============================================================================================================
def separate_room_building(usernames):
    command = {'message_type': 'SRB', 'owner': clientname, 'usernames': usernames.split()}
    return command

# ============================================================================================================
def separate_room_service(room_id, message):
    command = {'message_type': 'SRM', 'room_id': room_id, 'message': message}
    return command

# ============================================================================================================
def read_messages(message_type, timestamp):
    command = {'message_type': 'RDM', 'type': message_type, 'timestamp': timestamp}
    return command

# ============================================================================================================
def video_upload(udpSocket, audience, filename):
    if audience == clientname:
        print("Can't upload file to yourself!")
        return
    command = {'message_type': 'UDP', 'audience': audience, 'filename': filename}
    clientSocket.send(bytes(json.dumps(command),encoding='utf-8'))
    data = clientSocket.recv(1024)
    message = json.loads(data.decode('utf-8'))
    if message['response'] == 'OK':
        sendThread = Thread(target=send_file, args=(udpSocket, clientname, filename, message['message'][0][:-1], int(message['message'][1])))
        sendThread.start()
    else:
        print(message['message'])


# ============================================================================================================
def send_request(clientSocket, request):
    clientSocket.send(bytes(json.dumps(request),encoding='utf-8'))
    data = clientSocket.recv(1024)
    print(data.decode())

# ============================================================================================================
def connect_server(clientSocket, udp_port):
    send_login_info(clientSocket,udp_port)
    udpSocket = socket(AF_INET, SOCK_DGRAM)
    udpSocket.bind(('', udp_port))
    updThread = Thread(target=recv_file, args=(udpSocket,), daemon=True)
    updThread.start()
    print("Welcome to...")
    # idk why i spent time on this
    print("#######  ######  ######  #     # ")
    print("   #     #    #  #    #  ##   ## ")
    print("   #     #    #  #    #  # # # # ")
    print("   #     #    #  #    #  #  #  # ")
    print("   #     ######  ######  #  #  # teams + zoom wow")
    
    while True:
        command = input("Enter one of the following commands (BCM, ATU, SRB, SRM, RDM, OUT, UDP): \n")
        command_list = command.split()
        # Check if valid BCM command is entered
        if command_list[0] == "BCM" and len(command_list) > 1:
            message = command.split(' ', 1)[1]
            request = broadcast_message(message)
        # Check if ATU is entered
        elif command == "ATU":
            request = download_active_users()
        # Check if valid SRB command is entered
        elif "SRB" in command and len(command_list) > 1:
            usernames = command.split(' ', 1)[1]
            if clientname in usernames:
                print("Do not include your username in the usernames to add to the room!")
                continue
            request = separate_room_building(usernames)
        # Check if valid SRM command is entered
        elif command_list[0] == "SRM" and len(command_list) > 2:
            try:
                room_id = int(command_list[1])
            except ValueError:
                print("Please enter a valid room ID")
                continue
            message = ' '.join(command_list[2:])
            request = separate_room_service(room_id, message)
        # Check if valid RDM command is entered
        elif command_list[0] == "RDM" and (command_list[1] == 'b' or command_list[1] == 's') and len(command_list) > 2:
            timestamp = ' '.join(command_list[2:])
            try:
                datetime.strptime(timestamp, "%d %b %Y %H:%M:%S")
            except ValueError:
                print("Please enter timestamp in the format dd/mm/yyyy hh:mm:ss")
                continue
            request = read_messages(command_list[1], timestamp)
        # Check if OUT is entered
        elif command == "OUT":
            logout(udpSocket, clientSocket)
            continue
        # Check if valid UPD is entered
        elif command_list[0] == "UDP" and len(command_list) > 2:
            video_upload(udpSocket, command_list[1], command_list[2])
            continue
        # Invalid input/default error message
        else:
            print("Please enter a valid command")
            continue

        # Sends the information to the server
        send_request(clientSocket, request)
        

# ============================================================================================================
if __name__ == '__main__':
    if len(sys.argv) != 4:
        print("\n===== Error usage, python3 TCPServer3.py SERVER_IP SERVER_PORT UDP_PORT ======\n")
        exit()
    serverHost = str(sys.argv[1])
    serverPort = int(sys.argv[2])
    udp_port = int(sys.argv[3])

    # Initialise TCP connection
    clientSocket = socket(AF_INET, SOCK_STREAM)
    serverAddress = (serverHost, serverPort)
    clientSocket.connect(serverAddress)
    connect_server(clientSocket, udp_port)

