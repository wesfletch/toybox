#!/usr/bin/env python3

"""
FILE: Client.py
DESC: Functions intended to be used by the 'clients' of this library
      when interfacing with tbx.
"""

from dataclasses import dataclass, field
import grpc
import threading

from toybox_msgs.core.Client_pb2_grpc import ClientStub

from toybox_core.logging import LOG

@dataclass
class Client():
    client_id: str
    addr: str
    rpc_port: int
    data_port: int

    _mutex: threading.Lock = field(default_factory=threading.Lock)
    _channel: grpc.Channel | None = None
    _stub: ClientStub | None = None

    _initialized: bool = False

    def initialize(self) -> None:
        if self._initialized:
            return
        
        with self._mutex:
            if self._stub is None or self._channel is None:
                if self._channel is None:
                    LOG("DEBUG", f"Initializing channel for {self.client_id}")
                    self._channel = grpc.insecure_channel(f'{self.addr}:{self.rpc_port}')
                if self._stub is None:
                    LOG("DEBUG", f"Initializing stub for {self.client_id}")
                    self._stub = ClientStub(channel=self._channel)
        
        self._initialized = True
        LOG("DEBUG", f"Finished initializing client <{self.client_id}>")

    @property
    def channel(self) -> grpc.Channel:
        if not self._initialized:
            raise Exception(f"Client {self.client_id} not initialized.")
        with self._mutex:
            LOG("DEBUG", f"Getting channel for {self.client_id}")
            return self._channel

    @property
    def stub(self) -> ClientStub:
        if not self._initialized:
            raise Exception(f"Client {self.client_id} not initialized.")
        with self._mutex:
            LOG("DEBUG", f"Getting stub for {self.client_id}")
            return self._stub
