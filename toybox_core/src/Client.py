#!/usr/bin/env python3

from abc import ABC
import atexit
from dataclasses import dataclass, field
import errno
from queue import Queue, Empty
import socket
import sys
import threading
from typing import Dict, List, Union, Tuple

import grpc

# stupid hack because pip is the worst
sys.path.append('/home/dev/toybox')

from toybox_core.src.RegisterServer import (
    register_client_rpc,
    deregister_client_rpc
)


class MessageServer():

    def __init__(
        self,
        host: str = "localhost",
        port: int = 50505,
        sock: Union[socket.socket,None] = None,
    ) -> None:

        self._host: str = host
        self._port: int = port

        self._socket: Union[socket.socket,None] = sock

        self._inbound: Dict[socket.socket, Queue[str]] = {}
        self._outbound: Dict[socket.socket, Queue[str]] = {}

        # listen for incoming connections in separate thread
        self.listen_thread: threading.Thread = threading.Thread(target=self.listen)
        self.listen_thread.start()

    def listen(self) -> None:

        # enable socket to accept connections
        self._socket.listen()
        # make socket non-blocking
        self._socket.settimeout(0) 

        # listen for new connections to add to list
        while not is_shutdown():
            try:
                conn, addr = self._socket.accept()
                self._connections[conn] = Queue()
            except BlockingIOError:
                pass

    def handshake(self) -> None:

        pass

    def spin(
        self
    ) -> None:
        pass

class MessageHandshake():
    """
    Manages the lifetime of a handshake between a publisher and a subscriber.
    """
    def __init__(
        self, 
        topic_name: str, 
        message_type: str
    ) -> None:
        pass

    def next(self, input: str) -> None:
        
        if 




def port_in_use(port: int, host: str = 'localhost') -> bool:

    sock: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        sock.bind((host, port))
    except socket.error as e:
        if e.errno == errno.EADDRINUSE:
            return True
        # else:
        # should this handle other exceptions?
    sock.close()
    return False

def get_available_port(host: str = "localhost") -> int:

    port: int = 50505
    while port_in_use(port=port, host=host):
        port += 1
    return port

def is_shutdown() -> bool:
    return False

def deinit_node(
    name: str,
) -> None:
    
    deregister_client_rpc(name=name)

def init_node(
    name: str,
    address: Union[Tuple[str,int], None] = None,
    # standalone: bool = False,
) -> MessageServer:
    
    atexit.register(deinit_node, name)

    if not address:
        host: str = "localhost"
        port: int = get_available_port(host="localhost")
        address = (host, port)
    else:
        host, port = address

    sock: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if not port_in_use(port=port, host=host):
        try:
            sock.bind(address)
        except socket.error as e:
            # define custom exceptions/actually handle socket errors?
            raise Exception(e)
        
    # if not standalone:
    # register ourselves with the master
    if not register_client_rpc(name=name, addr=address):
        print("we fucked up, I guess")

    msg_server: MessageServer = MessageServer(host=host,
                                              port=port,
                                              sock=sock)
    
    return msg_server

def advertise_topic() -> None:




class ClientServicer():
    pass


def main():
    # msg_server: MessageServer = MessageServer()

    init_node(name="quetzal")

if __name__ == "__main__":
    main()