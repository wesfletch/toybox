#!/usr/bin/env python3

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import errno
from queue import Queue, Empty
import socket
import threading
from typing import TYPE_CHECKING, Dict, List, Tuple, Union, Callable
import uuid

from google.protobuf.message import Message, DecodeError

from toybox_core.src.TopicServer import Topic

class Transaction(ABC):

    def __init__(
        self, 
        name: str, 
        states: List[Tuple[str, str]],
    ) -> None:
        self._name = name
        self._states = states
        self._current_state = ""

    @property
    def name(self) -> str:
        return self._name
    @property
    def states(self) -> List[Tuple[str, str]]:
        return self._states
    @property
    def current_state(self) -> str:
        return self._current_state
    
    @abstractmethod
    def handle_message(
        self, 
        input: Message
    ) -> bool:
        raise NotImplementedError

@dataclass
class Connection():
    name: str
    sock: socket.socket
    host: str
    port: int

    initialized: bool = False

    inbound: "Queue[str]" = field(default_factory=Queue)
    outbound: "Queue[bytes]" = field(default_factory=Queue)

    in_lock: threading.Lock = threading.Lock()

    topic: Union[Topic, None] = None 

    def connect(self):

        self.sock.connect((self.host, self.port))
        self.initialized = True

    def wait_for_inbound(self, blocking: bool = True) -> bool:
        """Test synchronization"""
        if blocking:
            while self.inbound.qsize() == 0:
                continue
            return True
        else:
            return self.inbound.qsize() != 0
        
    def wait_for_outbound(self, blocking: bool = True) -> bool:
        "Test synchronization"
        if blocking:
            while self.outbound.qsize() != 0:
                # print(self.outbound.qsize())
                continue
            return True
        else:
            return self.inbound.qsize() == 0
        

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

def get_available_port(
    host: str = "localhost",
    start: int = 50505
) -> int:

    port: int = start
    while port_in_use(port=port, host=host):
        port += 1
    return port