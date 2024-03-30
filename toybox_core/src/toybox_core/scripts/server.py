#!/usr/bin/env python3

import atexit
from typing import Dict, List, Tuple, Union, Callable

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
import toybox_core as tbx

from toybox_msgs.core.Register_pb2_grpc import (
    add_RegisterServicer_to_server
)
from toybox_msgs.core.Topic_pb2_grpc import (
    add_TopicServicer_to_server
)


class ToyboxServer():

    def __init__(self):
        
        atexit.register(self.shutdown)

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

        self._server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        add_TopicServicer_to_server(
            self._topic_servicer,
            self._server
        )
        add_RegisterServicer_to_server(
            self._register_servicer,
            self._server
        )

        self._server.add_insecure_port('[::]:50051')
        
        LOG("INFO", f"Server configured for {self._server}")

    def serve(self):
        self._server.start()
        self._server.wait_for_termination()

    def shutdown(self):
        tbx.signal_shutdown()
        print(tbx.is_shutdown())

def main():

    tbx: ToyboxServer = ToyboxServer()
    tbx.serve()


if __name__ == "__main__":
    main()