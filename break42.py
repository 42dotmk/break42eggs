#!/bin/python
import socket
import os
import logging
import sys
import uuid
import threading
import random 
from typing import Tuple, List
from enum import Enum

logging.basicConfig(level=logging.WARN)

#envelope: [start] data [end]
#request: /[command] [args]
#response: [status] [response]
start = "[start]".encode()
end = "[end]".encode()
log = logging.getLogger("protocol")

def main():
    port = len(sys.argv) >= 3 and int(sys.argv[2]) or 42424
    host = len(sys.argv) >= 4 and sys.argv[3] or "ip.42.mk"
    is_server = len(sys.argv) >= 2 and sys.argv[1] == "server"
    func = is_server and server or client
    func(host, port)

def server(host='localhost', port=12345):
    players = []
    log = logging.getLogger("server")
    def handle_client(conn:socket.socket, addr):
        log.info("New connection %s connected.", addr)
        player = Player("Unknown")

        def send(data):
            log.info(f"Sending {data}")
            send_msg(conn, data)

        while True:
            ok, data = recv_msg(conn)
            if ok == MessageState.END_CONNECTION:
                log.error("Failed to read message")
                send("Failed to read message")
            elif data is None:
                log.error("Failed to read message")
                send("Failed to read message")
            elif data.startswith("/register"):
                name = data.split(" ")[1]
                player.name = name
                players.append(player)
                send(f"ok {player.pid}")
            elif data.startswith("/join"):
                pid = data.split(" ")[1]
                player = next((p for p in players if p.pid == pid), None)
                if player is None:
                    send("Error: Such player does not exist")
                else:
                    send(f"Welcome {player.name}, you have {player.points} points")
            elif data.startswith("/list"):
                sorted_players = sorted(players, key=lambda x: x.points, reverse=True)
                send("Leaderboard: \n============\n" + 
                      "\n".join([f"{'-' if player.egg is None else '+' } {player.name} at {player.points}" for player in sorted_players]))
            elif data.startswith("/break"):
                if " " not in data:
                    send("Usage: /break [player]")
                    continue
                other_name = data.split(" ")[1]
                other = next((p for p in players if p.name.lower() == other_name.lower()), None)
                if other is None:
                    send("Player not found")
                else:
                    send(player.break_egg(other))
            elif data.startswith("/buy"):
                player.buy_egg()
                send("Egg bought you can play again")
            elif data.startswith("/quit"):
                send("Goodbye")
                break
            else:
                send("Unknown command")

        print(f"Connection from {addr} has been closed.")
        conn.close()

    print("Starting server")
    server_socket = socket.socket()
    server_socket.bind((host, port))
    server_socket.listen(5)

    print(f"Server started. Listening on {host}:{port}")
    while True:
        conn, addr = server_socket.accept()
        log.info(f"Connection from {addr} has been established. Details: {conn}")
        threading.Thread(target=handle_client, args=(conn, addr)).start()

def client(host='localhost', port=12345):
    pid = None
    if os.path.exists("pid.txt"):
        with open("pid.txt", "r") as f:
            pid = f.read()
    name = None
    logging.basicConfig(level=logging.DEBUG)
    log = logging.getLogger(__name__)

    client_socket = socket.socket()
    client_socket.connect((host, port))

    
    def send(data):
        packages = wrap(data)
        log.info(f"sending {len(packages)}")
        for package in packages:
            client_socket.send(package)
        return recv_msg(client_socket)
    
    if pid is not None:
        ok, resp = send("/join " + pid)
        if ok == MessageState.DATA:
            print(resp)
            if resp is not None and resp.startswith("Welcome"):
                name = resp.split(" ")[1].split(",")[0].strip()

    while pid is None:
        name = input("Enter your Name: ")
        ok, resp = send("/register " + name)
        if not ok:
            log.error(f"Failed to register, try again")
            continue
        if not resp:
            log.error(f"Failed to register, try again")
            continue
        try:
            (ok, pid) = resp.split(" ")
            with open("pid.txt", "w") as f:
                f.write(pid)
        except:
            ok = "notok"
            log.error(f"Failed to register, try again")
        if ok == "ok":
            print(f"Registered with pid {pid}")
            print(f"Connected to server at {host}:{port} with username {name} and pid {pid}")
        else:
            log.error(f"Failed to register, try again")
            pid = None

    while True:
        data = input(f"list|buy|break|quit {name}> ")
        ok, resp = send("/"+data)
        if ok == MessageState.DATA:
            print(resp)
        else:
            break

class MessageState(Enum):
    DATA = 1
    END_CONNECTION = 2

class Player: 
    pid: str = str(uuid.uuid4())
    name: str = ""
    points: int = 9
    conn: socket.socket|None = None
    egg: Tuple[int, int]|None = (0, 0)
    broken_basket: List[Tuple[int, int]] = []

    def __init__(self, name):
        self.name = name

    def buy_egg(self):
        self.points -= 3
        if self.egg:
            self.broken_basket.append(self.egg)
        self.egg = (random.randint(0, 100), random.randint(0, 100))

    def break_egg(self,other):
        if self.egg is None:
            return "You have no egg to break, type /buy to buy an egg"
        if other.egg is None:
            return f"{other.name} has no egg to break, tell him to buy an egg and then try again"

        x2, y2 = other.egg
        x1, y1 = self.egg
        msg = ""

        if x1>x2 and y1>y2:
            self.points += 6
            other.points -= 3
            other.broken_basket.append(other.egg)
            other.egg = None
            msg = f"{self.name} broke {other.name}'s egg"

        elif x1<x2 and y1<y2:
            self.points -= 3
            other.points += 6
            self.broken_basket.append(self.egg)
            self.egg = None
            msg = f"{other.name} broke {self.name}'s egg"

        else:
            self.points += 3
            other.points += 3
            self.broken_basket.append(self.egg)
            other.broken_basket.append(other.egg)
            self.egg = None
            other.egg = None
            msg = f"{self.name} and {other.name} broke each other's egg its a draw"

        return msg

def send_msg(conn, data:str):
    """Sends the message to the connection"""
    packages = wrap(data)
    log.debug(f"Sending %s packages", len(packages))
    for package in packages:
        log.debug("Sending %s", package)
        conn.send(package)

def recv_msg(conn) -> Tuple[MessageState, str|None]:
    """Reads a message from the connection and returns a tuple of (status, data) 
    where status is True if the message is complete and False 
    if the message is incomplete. The data is the message itself."""
    data:bytes|None = None
    
    while True:
        chunk:bytes = conn.recv(1024)
        if not chunk:
            return MessageState.END_CONNECTION, None
        if data is None:
            data = chunk
        else:
            data+=chunk

        if data.endswith(end):
            return MessageState.DATA, unwrap(data)
        elif len(data) > 1024*1024:
            return MessageState.END_CONNECTION, "Message too long"

def split_bytes(data)->List[bytes]:
    """splits the bytes into a list of 1024 byte chunks"""
    return [data[i:i+1024] for i in range(0, len(data), 1024)]

def wrap(data:str)->List[bytes]:
    """Wraps the data in an envelope and returns the data encoded and ready to be sent."""
    log.debug(f"Wrapping {data}")
    return split_bytes(start + data.encode() + end)

def unwrap(data:bytes|None)->str|None:
    """Unwraps the decoded data from the envelope and returns the data itself."""
    log.debug("Unwrapping %s", data)
    if data is None:
        return None
    if not data.startswith(start) or not data.endswith(end):
        return None
    return data.decode()[7:-5]

if __name__ == '__main__':
    main()
