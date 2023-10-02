#!/usr/bin/env python3

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import errno
import grpc
from queue import Queue, Empty
import select
import socket
import struct
import sys
import time
import threading
from typing import TYPE_CHECKING, Dict, List, Tuple, Union, Callable, Type
import uuid

from google.protobuf.message import Message, DecodeError

# stupid hack because pip is the worst
sys.path.append('/home/dev/toybox')
from toybox_core.src.TopicServer import Topic, TopicServer, advertise_topic_rpc
from toybox_core.src.Logging import LOG
from toybox_msgs.core.Register_pb2 import ClientInfo, ClientMetadata
from toybox_msgs.core.Test_pb2 import TestMessage

@dataclass
class Connection():
    name: str
    sock: socket.socket
    host: str
    port: int
    initialized: bool = False
    inbound: "Queue[bytes]" = field(default_factory=Queue)
    outbound: "Queue[bytes]" = field(default_factory=Queue)
    lock: threading.Lock = threading.Lock()

    # thread management
    shutdown: bool = False

    # pub-sub
    topic: Union[Topic, None] = None

    def connect(self):

        self.sock.connect((self.host, self.port))
        self.initialized = True

    def listen(self) -> None:
        raise NotImplementedError
    
    def spin(self) -> None:
        raise NotImplementedError

    def read(self) -> bytes:
        
        # attempt to receive first 2 bytes of message
        try:
            len_bytes: bytes = self.sock.recv(2)
        except socket.error as e:
            # if e.errno == 107: # transport endpoint not connected
            raise e

        # unpack (L)ength -> first two bytes
        data_len: int = struct.unpack("H", len_bytes)[0]
        # receive (T)ype and (V)alue
        received: bytes = self.sock.recv(data_len)

        return received

    @classmethod
    def pack_message(
        self,
        message: Message,
    ) -> bytes:
        """
        Package a pb2 object into a `bytes` message ready for socket transmission. 
        Messages are in Length-Type-Value (LTV) format.

        Args:
            message (Message): message (pb2) to package into LTV format
        """

        # pack (T)ype and (V)alue
        LOG("DEBUG", f"packing <{message.DESCRIPTOR.full_name}>")
        message_type: bytes = message.DESCRIPTOR.full_name.encode('utf-8')
        LOG("DEBUG", f"sending message type <{message_type!r}>")
        message_bytes: bytes = message.SerializeToString()

        # prepend messages with (L)ength
        data_len = struct.pack("H", len(message_type) + len(message_bytes))
        
        # pack bytes
        packed_message: bytearray = bytearray()
        packed_message += data_len
        packed_message += message_type
        packed_message += message_bytes

        return bytes(packed_message)
    
    @classmethod
    def split_message(
        self,
        message: bytes
    ) -> Tuple[bytes, bytes]:
        """
        Assumes that Length bytes (first 2) have already been removed.

        Args:
            message (bytes): a `bytes` message to be split

        Returns:
            Tuple[bytes, bytes]: (message_type, message_data)
        """
        msg_split = message.splitlines(keepends=True)
        message_type: str = msg_split[0].decode('utf-8')
        message_type = message_type.rstrip('\n')
        message_data: bytes = b'\n' + b''.join(msg_split[1:])

        return (message_type, message_data)

    @classmethod
    def unpack_message(
        self,
        obj_type: Type[Message], 
        message_data: bytes
    ) -> Message:

        message: 'obj_type' = obj_type()
        try:
            message.ParseFromString(message_data)
        except DecodeError as e:
            LOG("ERR",f"We just got garbage: {e}")
            raise e
        
        return message

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
        
class Publisher(Connection):

    def __init__(self, topic_name: str, message_type: str, host: str, port: int) -> None:
        Connection.__init__(
            self,
            name=f"publisher_{topic_name}_{str(uuid.uuid1())}",
            sock=socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM),
            host=host,
            port=port,
            topic=Topic(name=topic_name, message_type=message_type)
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
                LOG("DEBUG", f"<{self.name}> accepted conn request from {conn.getpeername()}")
                with self.lock:
                    subscriber: Connection = Connection(name="", sock=conn,
                                                        host=addr[0], port=addr[1],)                
                    self._subscribers.append(subscriber)
            except BlockingIOError:
                continue

            time.sleep(0.001)

        self.sock.shutdown(socket.SHUT_RDWR)
        self.sock.close()
        # signal that we've properly closed the socket
        self._listen_shutdown.set()

    # threading.Thread
    def spin(self) -> None:

        while not self.shutdown:
            if len(self._subscribers) == 0:
                continue

            try:
                message: bytes = self.outbound.get(block=False)
            except Empty:
                continue
            
            for subscriber in self._subscribers:
                subscriber.sock.sendall(message)

            time.sleep(0.001)
        
        self._spin_shutdown.set()

    def advertise(self) -> None:

        # advertise the topic to the TopicServer
        try:
            advertise_topic_rpc(
                client_name=self.name,
                client_host=self.host,
                topic_port=self.port,
                topic_name=self.topic.name,
                message_type=self.topic.message_type
            )
        except grpc.RpcError as rpc_error:
            LOG("ERR", f"that didn't work: {rpc_error}")
            return False

    def publish(self, message: Message) -> None:

        if message.DESCRIPTOR.full_name != self.topic.message_type:
            raise Exception("invalid message type")
        
        packed_message: bytes = self.pack_message(message)

        self.outbound.put(packed_message)


class Subscriber(Connection):

    def __init__(
        self,
        topic_name: str,
        message_type: str,
        host: str,
        port: int,
        publisher_info: Union[None,Tuple[str,str,int]] = None,
        callback: Union[Callable,None] = None,
    ) -> None:
        Connection.__init__(
            self,
            name=f"subscriber_{topic_name}_{str(uuid.uuid1())}",
            sock=socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM),
            host=host,
            port=port,
            topic=Topic(name=topic_name, message_type=message_type),
        )
        print(f"{self.host}, {self.port}")
        self.sock.bind((self.host, self.port))
        
        self._callbacks: List[Callable] = [callback] if callback else []
        
        self._publisher = publisher_info
        if self._publisher is not None:
            self.connect_to_publisher(publisher_info)

        self._spin_thread: threading.Thread = threading.Thread(target=self.spin)
        self._spin_thread.start()

    # threading.Thread
    def spin(self) -> None:

        while not self.shutdown:
            if self._publisher is None:
                continue
            
            # get available [in/out]bound sockets
            ready_to_read, _, _ = select.select([self.sock], [], [], 0)
            if self.sock in ready_to_read:    
                message: bytes = self.read()
                split_message: Tuple[bytes,bytes] = self.split_message(message)
                self.inbound.put(split_message[1])
            
            try:
                message_bytes: bytes = self.inbound.get(block=False)
            except Empty:
                continue
           
            # TODO: carry around message type as an object, NOT as a string to avoid hard-coding like this
            message_obj: Message = self.unpack_message(obj_type=TestMessage, message_data=message_bytes)
            
            for callback in self.callbacks:
                callback(message_obj)

            time.sleep(0.001)
    
    # def look_for_publishers(self) -> None:
    #     pass

    def connect_to_publisher(self, publisher_info: Tuple[str,str,int]) -> None:

        # attempt to connect to publisher using provided info
        pub_host: str = publisher_info[1]
        pub_port: int = publisher_info[2]
        self.sock.connect((pub_host, pub_port))

        # # now, we should introduce ourselves (to be polite)'
        # intro_msg: ClientInfo = ClientInfo()
        # intro_msg.client_id = self.name
        # metadata: ClientMetadata = ClientMetadata()
        # metadata.addr = self.sock.getsockname()[0]
        # metadata.port = self.sock.getsockname()[1]
        # intro_msg.meta.CopyFrom(metadata)

    @property
    def publisher(self) -> List[Connection]:
        # get mutex?
        return self._publisher
    
    @property
    def callbacks(self) -> List[Callable]:
        return self._callbacks
    
    def add_publisher(self, publisher_id: str) -> None:
        pass

    
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

def test_callback(message: TestMessage) -> None:
    print("callback fired: ")
    print(message)

def main() -> None:
    
    topic_server: TopicServer = TopicServer()
    server_thread: threading.Thread = threading.Thread(target=topic_server.serve)
    server_thread.start()

    # wait for server to be ready before continuing
    while topic_server.not_started:
        continue

    publisher: Publisher = Publisher(
        topic_name="butts",
        message_type="core.TestMessage",
        host="localhost",
        port=get_available_port("localhost", start=50554)
    )
    publisher.advertise()

    subscriber: Subscriber = Subscriber(
        topic_name="butts",
        message_type="core.TestMessage",
        host="localhost",
        port=get_available_port("localhost", start=50555),
        publisher_info=(publisher.name, publisher.host, publisher.port),
        callback=test_callback
    )

    test_message: TestMessage = TestMessage(test_string="rrrr")
    publisher.publish(test_message)

    server_thread.join()

if __name__ == "__main__":
    main()