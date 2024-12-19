#!/usr/bin/env python3

import atexit
import signal
import sys
from typing import Dict

import grpc
import concurrent.futures as futures

from toybox_core.TopicServer import (
    Topic,
    TopicRPCServicer
)
from toybox_core.RegisterServer import (
    Client,
    RegisterServicer
)
from toybox_core.Logging import LOG

from toybox_msgs.core import Client_pb2_grpc
from toybox_msgs.core.Null_pb2 import Null
from toybox_msgs.core.Register_pb2_grpc import (
    add_RegisterServicer_to_server
)
from toybox_msgs.core.Topic_pb2_grpc import (
    add_TopicServicer_to_server
)


class ToyboxServer():

    def __init__(self):
        
        self._topics: Dict[str,Topic] = {}
        self._clients: Dict[str,Client] = {}

        self._topic_servicer: TopicRPCServicer = TopicRPCServicer(
            topics=self._topics,
            clients=self._clients
        )
        self._register_servicer: RegisterServicer = RegisterServicer(
            clients=self._clients,
            topics=self._topics
        )

        self._server: grpc.Server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        add_TopicServicer_to_server(
            self._topic_servicer,
            self._server
        )
        add_RegisterServicer_to_server(
            self._register_servicer,
            self._server
        )

        self._server.add_insecure_port('[::]:50051')
        
        LOG("INFO", f"Server configured for {str(self._server)}")
        
        atexit.register(self.shutdown)
        signal.signal(signal.SIGINT, self.ctrl_c_handler)

    def serve(self) -> None:
        self._server.start()
        self._server.wait_for_termination()

    def shutdown(self) -> None:
        """
        Send the shutdown signal to any registered clients.
        """

        channel: grpc.insecure_channel
        client_stub: Client_pb2_grpc.ClientStub
        
        for name, client in self._clients.items():
            LOG("INFO", f"Sent shutdown request to {name} at {client.addr}:{client.rpc_port}")
            channel = grpc.insecure_channel(f'{client.addr}:{client.rpc_port}')
            client_stub = Client_pb2_grpc.ClientStub(channel=channel)
            
            # Actually send the Shutdown() request to the client,
            # but use a timeout because we don't actually care about their response.
            shutdown_req: Null = Null()
            client_stub.InformOfShutdown(request=shutdown_req, timeout=1.0)

    def ctrl_c_handler(self, signum, frame) -> None:
        self.shutdown()
        sys.exit(0)

def main():

    tbx: ToyboxServer = ToyboxServer()
    tbx.serve()

if __name__ == "__main__":
    main()