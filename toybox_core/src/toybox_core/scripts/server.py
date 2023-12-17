#!/usr/bin/env python3

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

from toybox_msgs.core.Register_pb2_grpc import (
    add_RegisterServicer_to_server
)
from toybox_msgs.core.Topic_pb2_grpc import (
    add_TopicServicer_to_server
)

# TODO: transition to "monolithic" server
#       need central store of info for Topics + Clients at least
class ToyboxServer():

    def __init__(self):
        
        self._topics: Dict[str, Topic] = {}
        self._clients: Dict[str,Client] = {}

        self._server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        self._topic_servicer: TopicRPCServicer = TopicRPCServicer(topics=self._topics)
        self._register_servicer: RegisterServicer = RegisterServicer(clients=self._clients)

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


def main():

    tbx: ToyboxServer = ToyboxServer()
    tbx.serve()


if __name__ == "__main__":
    main()