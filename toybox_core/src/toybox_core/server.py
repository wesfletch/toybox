#!/usr/bin/env python3

import atexit
import concurrent.futures as futures
import grpc
from queue import Queue, Empty
import signal
import sys
import threading
import time

from toybox_core.client import Client
from toybox_core.launchable import Launchable
from toybox_core.logging import LOG
from toybox_core.topic import Topic
from toybox_core.rpc.health import HealthRPCServicer
from toybox_core.rpc.topic import TopicRPCServicer
from toybox_core.rpc.register import RegisterServicer

from toybox_msgs.core.Health_pb2_grpc import add_HealthServicer_to_server
from toybox_msgs.core.Node_pb2 import InformConfirmation, TopicPublisherInfo
from toybox_msgs.core.Topic_pb2_grpc import add_TopicServicer_to_server
from toybox_msgs.core.Register_pb2_grpc import add_RegisterServicer_to_server
from toybox_msgs.core.Null_pb2 import Null


DEFAULT_TBX_SERVER_HOST: str = "localhost"
DEFAULT_TBX_SERVER_PORT: int = 50051


class ToyboxServer(Launchable):

    def __init__(self, port: int | None = None) -> None:
        
        self._name: str = "tbx-server"

        # "Context" that will be handed to RPC servicers
        self._topics: dict[str,Topic] = {}
        self._clients: dict[str,Client] = {}
        self._announcements: Queue[tuple[str,str]] = Queue()

        self._client_lock: threading.Lock = threading.Lock()

        # RPC servicers
        self._health_servicer: HealthRPCServicer = HealthRPCServicer()
        self._topic_servicer: TopicRPCServicer = TopicRPCServicer(
            topics=self._topics,
            clients=self._clients,
            announcements=self._announcements)
        self._register_servicer: RegisterServicer = RegisterServicer(
            clients=self._clients,
            topics=self._topics,
            deregister_callback=self.deregister_client)

        self._server: grpc.Server = grpc.server(futures.ThreadPoolExecutor(max_workers=None))
        add_HealthServicer_to_server(
            servicer=self._health_servicer,
            server=self._server)
        add_TopicServicer_to_server(
            servicer=self._topic_servicer,
            server=self._server)
        add_RegisterServicer_to_server(
            servicer=self._register_servicer,
            server=self._server)

        self.rpc_port: int = port if port else DEFAULT_TBX_SERVER_PORT
        rpc_port: int = self._server.add_insecure_port(f'[::]:{self.rpc_port}')
        
        LOG("INFO", f"Server <{self._name}> ready on port {rpc_port}.")
        
        atexit.register(self.shutdown)
        signal.signal(signal.SIGINT, self.ctrl_c_handler)

        self._shutdown_event: threading.Event = threading.Event()

    def launch(self) -> bool:
        self.serve()
        return True

    def serve(self) -> None:

        self._server.start()
        # self._server.wait_for_termination()
        self.spin()

    def spin(self) -> None:

        while not self._shutdown_event.is_set():
            
            self._announce_new_topics()
            
            time.sleep(1/60)
        
    def shutdown(self, notify_clients: bool = True) -> None:
        """
        Send the shutdown signal to any registered clients.
        """
        if self._shutdown_event.is_set():
            return

        self._shutdown_event.set()

        if not notify_clients:
            return

        for name, client in self._clients.items():       
            # Actually send the Shutdown() request to the client,
            # but use a timeout because we don't care about their response.
            shutdown_req: Null = Null()
            try:
                client.stub.InformOfShutdown(request=shutdown_req, timeout=0.25)
            except grpc.RpcError as e:
                if e == grpc.StatusCode.DEADLINE_EXCEEDED:
                    # We don't care...
                    continue

            LOG("INFO", f"Sent shutdown request to {name} at {client.addr}:{client.rpc_port}")

        self._server.stop(grace=2.0)

    def ctrl_c_handler(self, signum, frame) -> None:
        self.shutdown()
        sys.exit(0)

    def deregister_client(self, client_name: str) -> bool:
        """
        Callback for deregistering clients; handles removing the client itself,
        as well as cleaning out any topics, ..., etc. that may be attached to it.
        """

        # A topic with no publishers and no subscribers is an orphan,
        # and orphans have got to go.
        orphans: list[str] = []

        # Get rid of the client...
        with self._client_lock:
            del self._clients[client_name]

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
    
    def _announce_new_topics(self) -> None:

        try:
            announcement: tuple[str,str] = self._announcements.get(block=False)
        except Empty:
            return
        
        publisher_name: str = announcement[0]
        topic_name: str = announcement[1]
        
        LOG("DEBUG", f"Announcing new topic {topic_name} from publisher {publisher_name}")
        topic: Topic | None = self._topics.get(topic_name)
        if topic is None:
            raise Exception(f"Tried to announce topic that doesn't exist: {topic_name}")
        
        publisher_addr: tuple[str,int] | None = topic.publishers.get(publisher_name, None)
        assert publisher_addr is not None
        
        for subscriber_name in topic.subscribers:
            # Special case: a node advertises a topic that it's also subscribed to.
            # TODO: For now, skip it. May need to actually handle this in the future.
            if subscriber_name == publisher_name:
                continue

            LOG("DEBUG", f"Informing subscriber {subscriber_name} of topic {topic_name}")

            subscriber: Client | None = None
            with self._client_lock:
                subscriber = self._clients.get(subscriber_name, None)
            
            if subscriber is None:
                LOG("ERR", f"Subscriber {subscriber_name} is not a registered client.")
                raise Exception(f"Tried to inform a subscriber that doesn't exist: {subscriber_name}")

            topic_pub: TopicPublisherInfo = TopicPublisherInfo()
            topic_pub.topic_def.CopyFrom(topic.to_msg())
            topic_pub.publisher.publisher_id = publisher_name
            topic_pub.publisher.publisher_host = publisher_addr[0]
            topic_pub.publisher.topic_port = publisher_addr[1]

            # TEMP: just retry the InformOfPublisher RPC later if this fails
            try:
                inform_conf: InformConfirmation = subscriber.stub.InformOfPublisher(topic_pub, timeout=1.0)
            except grpc.RpcError as e:
                print(f"fuck: {e}")
                self._announcements.put(announcement)
                continue

            if inform_conf.return_code != 0:
                raise Exception(f"Failed to inform subscriber {subscriber_name} of topic {topic.name}: {inform_conf.status}")
            LOG("DEBUG", f"Successfully informed <{subscriber_name}> of <{topic_name}>")

