#!/usr/bin/env python3

import atexit
import signal
import sys
import threading
import time
from typing import Dict, List

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

    def __init__(self) -> None:
        
        self._topics: Dict[str,Topic] = {}
        self._clients: Dict[str,Client] = {}

        self._topic_servicer: TopicRPCServicer = TopicRPCServicer(
            topics=self._topics,
            clients=self._clients
        )
        self._register_servicer: RegisterServicer = RegisterServicer(
            clients=self._clients,
            topics=self._topics,
            deregister_callback=self.deregister_client
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

        rpc_port: int =  self._server.add_insecure_port('[::]:50051')
        
        LOG("INFO", f"Server configured for {str(self._server)} on port {rpc_port}")
        
        atexit.register(self.shutdown)
        signal.signal(signal.SIGINT, self.ctrl_c_handler)

        self._shutdown_event: threading.Event = threading.Event()

    def serve(self) -> None:

        self._server.start()
        self._server.wait_for_termination()


    def shutdown(self) -> None:
        """
        Send the shutdown signal to any registered clients.
        """
        print("SHUTDOWN GOT CALLED")

        if self._shutdown_event.is_set():
            return

        for name, client in self._clients.items():
            client_stub = client.get_stub()
            
            # Actually send the Shutdown() request to the client,
            # but use a timeout because we don't care about their response.
            shutdown_req: Null = Null()
            try:
                client_stub.InformOfShutdown(request=shutdown_req, timeout=0.25)
            except grpc.RpcError as e:
                if e == grpc.StatusCode.DEADLINE_EXCEEDED:
                    # We don't care...
                    continue

            LOG("INFO", f"Sent shutdown request to {name} at {client.addr}:{client.rpc_port}")

        self._shutdown_event.set()

    def ctrl_c_handler(self, signum, frame) -> None:
        self.shutdown()
        sys.exit(0)

    def deregister_client(self, client_name: str) -> bool:
        """
        Callback for deregistering clients; handles removing the client itself,
        as well as cleaning out any topics, ..., etc. that may be attached to it.
        """

        # Get rid of the client...
        del self._clients[client_name]

        # A topic with no publishers and no subscribers is an orphan,
        # and orphans have got to go.
        orphans: List[str] = []

        # And make sure that any topics that it was subscribed to/advertising go away as well.
        for topic_name, topic in self._topics.items():
            if topic.publishers.get(client_name, None) is not None:
                del topic.publishers[client_name]
            if client_name in topic.subscribers:
                topic.subscribers.remove(client_name)

            # Is this an orphan? Put its name in the death note.
            if len(topic.publishers) == 0 and len(topic.subscribers) == 0:
                orphans.append(topic_name)
        
        # Get rid of any orphans.
        for orphan in orphans:
            del self._topics[orphan]

        return True

def main() -> None:

    tbx: ToyboxServer = ToyboxServer()
    tbx.serve()

if __name__ == "__main__":
    main()