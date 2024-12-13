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
        request: TopicDefinition, 
        context: grpc.ServicerContext,
    ) -> Client_pb2.InformConfirmation:
        
        publisher_uuid: str = request.uuid
        topic: str = request.topic_name
        message_type: str = request.message_type

        # look to see if we have a subscriber that cares about this topic
        subscription: Subscriber | None = None
        for sub in self._subscribers:
            if sub.topic.name == topic:
                subscription = sub

        # first, make sure we actually care about this message
        if subscription is None:
            return Client_pb2.InformConfirmation(
                return_code=1,
                status="I don't think I asked for this."
            )
        # and message type is correct
        if subscription.topic.message_type.DESCRIPTOR.full_name != message_type:
            return Client_pb2.InformConfirmation(
                return_code=2,
                status=f"Unexpected message type {message_type}, expected {subscription.message_type}"
            )

        subscription.add_publisher(publisher_uuid)
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
