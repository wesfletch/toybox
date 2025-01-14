#!/usr/bin/env python3

import grpc
from typing import Any, Callable

from toybox_core.connection import Subscriber
from toybox_core.logging import TbxLogger, LOG

import toybox_msgs.core.Node_pb2 as Node_pb2
from toybox_msgs.core.Node_pb2_grpc import NodeServicer
from toybox_msgs.core.Null_pb2 import Null


class NodeRPCServicer(NodeServicer):
    """
    The NodeRPCServicer services RPCs sent to toybox client nodes.
    """

    def __init__(
        self, 
        subscribers: list[Subscriber],
        shutdown_callback: Callable,
        logger: TbxLogger | None = None
    ) -> None:
        
        self._subscribers: list[Subscriber] = subscribers

        # The shutdown callback is called when we receive an InformOfShutdown RPC.
        self._shutdown_callback: Callable[[bool],Any] = shutdown_callback

        self.logger: TbxLogger = logger if logger else TbxLogger()

    def InformOfPublisher(
        self, 
        request: Node_pb2.TopicPublisherInfo, 
        context: grpc.ServicerContext,
    ) -> Node_pb2.InformConfirmation:
        
        self.logger.LOG("DEBUG", f"Got InformOfPublisher RPC {request.publisher}")
        topic_name: str = request.topic_def.topic_name
        message_type: str = request.topic_def.message_type
        publisher_id: str =  request.publisher.publisher_id
        publisher_host: str = request.publisher.publisher_host
        publisher_port: int = request.publisher.topic_port

        # Check if we have subscriber(s) for this topic.
        subscribers: list[Subscriber] = []
        for sub in self._subscribers:
            if sub.topic.name == topic_name:
                subscribers.append(sub)

        if len(subscribers) == 0:
            self.logger.LOG("DEBUG", f"SUBSCRIBERS: {self._subscribers}")
            # The server shouldn't be sending us these unless we previously subscribed
            # to this topic, so not having a Subscriber for the topic constitutes an error.
            return Node_pb2.InformConfirmation(
                return_code=1,
                status="Not subscribed to this topic.")

        # Add the publisher info to subscriber(s).
        for subscriber in subscribers:
            if subscriber.topic.message_type.DESCRIPTOR.full_name != message_type:
                return Node_pb2.InformConfirmation(
                    return_code=2,
                    status=f"Unexpected message type {message_type}, expected {subscriber.topic.message_type}")
            self.logger.LOG("DEBUG", f"Adding publisher {publisher_id} to subscriber.")
            subscriber.add_publisher((publisher_id, publisher_host, publisher_port))
        
        return Node_pb2.InformConfirmation(return_code=0)

    def InformOfShutdown(
        self, 
        request: Null, 
        context: grpc.ServicerContext
    ) -> Null:
        
        self._shutdown_callback(True)        
        # This may or may not ever get back to the caller, which doesn't matter
        # since the caller won't be waiting for the response anyway.
        return Null()
