#!/usr/bin/env python3

import grpc
from typing import Callable, List

from toybox_core.Connection import Subscriber

import toybox_msgs.core.Client_pb2 as Client_pb2
import toybox_msgs.core.Client_pb2_grpc as Client_pb2_grpc
from toybox_msgs.core.Client_pb2_grpc import ClientServicer
from toybox_msgs.core.Topic_pb2 import TopicDefinition
from toybox_msgs.core.Null_pb2 import Null

class ClientRPCServicer(ClientServicer):

    def __init__(
        self, 
        subscribers: List[Subscriber],
        shutdown_callback: Callable,
    ) -> None:
        
        self._subscribers: List[Subscriber] = subscribers

        self._shutdown_callback: Callable = shutdown_callback

    def InformOfPublisher(
        self, 
        request: Client_pb2.TopicPublisherInfo, 
        context: grpc.ServicerContext,
    ) -> Client_pb2.InformConfirmation:

        topic_name: str = request.topic_def.topic_name
        message_type: str = request.topic_def.message_type
        publisher_id: str =  request.publisher.publisher_id
        publisher_host: str = request.publisher.publisher_host
        publisher_port: int = request.publisher.topic_port

        # look to see if we have a subscriber that cares about this topic
        subscriber: Subscriber | None = None
        for sub in self._subscribers:
            if sub.topic.name == topic_name:
                subscriber = sub

        # first, make sure we actually care about this message
        if subscriber is None:
            return Client_pb2.InformConfirmation(
                return_code=1,
                status="Not subscribed to this topic."
            )
        assert subscriber is not None
        # and message type is correct
        if subscriber.topic.message_type.DESCRIPTOR.full_name != message_type:
            return Client_pb2.InformConfirmation(
                return_code=2,
                status=f"Unexpected message type {message_type}, expected {subscriber.topic.message_type}"
            )

        subscriber.add_publisher((publisher_id, publisher_host, publisher_port))
        return Client_pb2.InformConfirmation(
            return_code=0,
        )
    
    def InformOfShutdown(
        self, 
        request: Null, 
        context: grpc.ServicerContext
    ) -> Null:
        
        print(f"Calling the shutdown callback...")
        self._shutdown_callback(True)
        
        # This may or may not ever get back to the caller, which doesn't matter
        # since the caller won't be waiting for the response anyway.
        return Null()
