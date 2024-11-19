#!/usr/bin/env python3

from dataclasses import dataclass, field
import enum
import errno
from queue import Queue, Empty
import select
import socket
import time
import threading
from typing import TYPE_CHECKING, Dict, List, Tuple, Union, Callable, Type, Any
import uuid

import grpc
from google.protobuf.message import Message

from toybox_core.Logging import LOG, TbxLogger
import toybox_core.protocol
from toybox_core.protocol import TbxMessage
from toybox_core.Topic import Topic
from toybox_core.TopicServer import advertise_topic_rpc

class Connection_State(enum.Enum):
    NOT_CONNECTED = 1
    CONNECTED = 2
    DISCONNECTED = 3

@dataclass
class Connection():
    name: str
    sock: socket.socket
    host: str
    port: int
    initialized: bool = False
    inbound: "Queue[bytes]" = field(default_factory=Queue)
    outbound: "Queue[bytes]" = field(default_factory=Queue)
    lock: threading.Lock = field(default_factory=threading.Lock)
    logger: TbxLogger | None = None
    # thread management
    shutdown: bool = False
    # pub-sub
    topic: Topic | None = None
    # number of failures to receive/send since last success
    failures: int = 0

    def connect(self) -> None:

        self.sock.connect((self.host, self.port))
        self.initialized = True

    def listen(self) -> None:
        raise NotImplementedError
    
    def spin(self) -> None:
        raise NotImplementedError

    def log(
        self, 
        log_level: str, 
        message: str,
    ) -> None:
        if self.logger is not None:
            self.logger.LOG(log_level=log_level, message=message)
        else:
            LOG(log_level=log_level, message=message)

    def wait_for_inbound(self, blocking: bool = True) -> bool:
        """Test synchronization"""
        if blocking:
            while self.inbound.qsize() == 0:
                continue
            return True
        else:
            return self.inbound.qsize() != 0
        
    def wait_for_outbound(self, blocking: bool = True) -> bool:
        """Test synchronization"""
        if blocking:
            while self.outbound.qsize() != 0:
                continue
            return True
        else:
            return self.inbound.qsize() == 0
        
class Publisher(Connection):

    def __init__(
        self, 
        topic_name: str, 
        message_type: Message, 
        host: str, 
        port: int,
        logger: TbxLogger | None = None
    ) -> None:

        Connection.__init__(
            self,
            name=f"publisher_{topic_name}_{str(uuid.uuid1())}",
            sock=socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM),
            host=host,
            port=port,
            topic=Topic(name=topic_name, message_type=message_type),
            logger=logger
        )
        self.sock.bind(('', self.port))

        self.topic: Topic # type-hinting shenanigans

        self._subscribers: List[Connection] = []

        self._listen_thread: threading.Thread = threading.Thread(target=self.listen)
        self._listen_shutdown: threading.Event = threading.Event()
        self._listen_thread.start()

        self._spin_thread: threading.Thread = threading.Thread(target=self.spin)
        self._spin_shutdown: threading.Event = threading.Event()
        self._spin_thread.start()

    # threading.Thread
    def listen(self) -> None:

        # enable socket to accept connections
        self.sock.listen()
        # make socket non-blocking
        self.sock.settimeout(0)

        while not self.shutdown:
            try:
                conn, addr = self.sock.accept()
                self.log("DEBUG", f"<{self.name}> accepted conn request from {conn.getpeername()}")
                with self.lock:
                    subscriber: Connection = Connection(
                        name="", 
                        sock=conn,
                        host=addr[0], 
                        port=addr[1],
                    )                
                    self._subscribers.append(subscriber)
            except BlockingIOError:
                time.sleep(0.1)

        self.sock.shutdown(socket.SHUT_RDWR)
        self.sock.close()
        # signal that we've properly closed the socket
        self._listen_shutdown.set()

    # threading.Thread
    def spin(self) -> None:

        while not self.shutdown:
            # rate-limit to prevent 100% CPU usage
            time.sleep(0.01)

            try:
                message: bytes = self.outbound.get(block=False)
            except Empty:
                continue
            
            for subscriber in self._subscribers:
                
                try:
                    subscriber.sock.sendall(message)
                    # If we send successfully (don't throw socket error),
                    # reset our failure counter
                    subscriber.failures = 0
                except socket.error:
                    subscriber.failures +=1

                # TODO: would be smarter to do this with a timeout, rather than a raw counter
                # since messages can happen so fast
                if subscriber.failures > 3:
                    self._subscribers.remove(subscriber)
                    self.log("WARN", f"Removed subscriber <{subscriber.name}> after too many failed sends.")

        self._spin_shutdown.set()

    def advertise(
        self, 
        advertiser_id: str | None
    ) -> bool:

        # advertise the topic to the TopicServer
        try:
            result: bool = advertise_topic_rpc(
                client_name=advertiser_id if advertiser_id else self.name,
                client_host=self.host,
                topic_port=self.port,
                topic_name=self.topic.name,
                message_type=self.topic.message_type
            )
        except grpc.RpcError as e:
            self.log("ERR", f"that didn't work: {e}")
            raise e
        
        return result

    def publish(
        self, 
        message: Message
    ) -> None:

        if message.DESCRIPTOR.full_name != self.topic.message_type.DESCRIPTOR.full_name:
            raise Exception("invalid message type")

        # don't bother packing messages for nobody
        # TODO: maybe latch???
        if len(self._subscribers) == 0:
            return

        packed_message: bytes = toybox_core.protocol.pack_message(message)

        self.outbound.put(packed_message)


class Subscriber(Connection):

    def __init__(
        self,
        topic_name: str,
        message_type: Message,
        host: str,
        port: int,
        publisher_info: Tuple[str,str,int] | None = None,
        callback: Callable[[Message], None] | None = None,
        logger: TbxLogger | None = None
    ) -> None:
        
        Connection.__init__(
            self,
            name=f"subscriber_{topic_name}_{str(uuid.uuid1())}",
            sock=socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM),
            host=host,
            port=port,
            topic=Topic(name=topic_name, message_type=message_type),
            logger=logger
        )
        self.sock.bind((self.host, self.port))
        
        self.topic: Topic

        self._callbacks: List[Callable[[Message], None]] = [callback] if callback else []
        
        self._publisher = publisher_info
        if self._publisher is not None:
            self.connect_to_publisher(self._publisher)

        self._spin_thread: threading.Thread = threading.Thread(target=self.spin)
        self._spin_thread.start()

    # threading.Thread
    def spin(self) -> None:

        while not self.shutdown:
            time.sleep(0.01)
            
            if self._publisher is None:
                continue
            
            # Get available [in/out]bound sockets
            ready_to_read, _, _ = select.select([self.sock], [], [], 0)
            if self.sock in ready_to_read:    
                message: TbxMessage | None = toybox_core.protocol.read(self.sock)
                if message is None:
                    continue

                LOG("DEBUG", f"Message read was: <{message.message_raw}>")
                split_message: Tuple[str,bytes] = \
                    toybox_core.protocol.split_message(message.message_raw, 
                                                       message.type_length, 
                                                       message.payload_length)
                LOG("DEBUG", f"Putting message in inbound queue: <{split_message[1].hex()}>")
                self.inbound.put(split_message[1])
            
            try:
                message_bytes: bytes = self.inbound.get(block=False)
            except Empty:
                continue
  
            LOG("DEBUG", f"Pulling message from inbound queue <{message_bytes.hex()}>")
            unpacked_msg: Message = toybox_core.protocol.unpack_message(
                obj_type=self.topic.message_type, 
                message_data=message_bytes
            )
            
            # TODO: could get more robust with callbacks
            for callback in self.callbacks:
                callback(self, message=unpacked_msg)


    def connect_to_publisher(
        self, 
        publisher_info: Tuple[str,str,int]
    ) -> None:

        pub_host: str = publisher_info[1]
        pub_port: int = publisher_info[2]
        self.sock.connect((pub_host, pub_port))

    @property
    def publisher(self) -> Tuple[str,str,int] | None:
        # get mutex?
        return self._publisher
    
    @property
    def callbacks(self) -> List[Callable[[Message], None]]:
        return self._callbacks
    
    def add_publisher(self, publisher_id: str) -> None:
        pass

    
def port_in_use(
    port: int, 
    host: str = 'localhost'
) -> bool:

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

