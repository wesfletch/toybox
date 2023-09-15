#!/usr/bin/env python3

from typing import Dict, List, Union, Tuple, Callable
from toybox_core.src.TopicServer import (
    Topic,
)

import toybox_msgs.core.Client_pb2 as Client_pb2
from toybox_msgs.core.Client_pb2_grpc import (
    ClientServicer,
    add_ClientServicer_to_server,
)
from toybox_msgs.core.Topic_pb2 import (
    SubscriberList,
    TopicDefinition,
)

import toybox_msgs.core.Topic_pb2 as Topic_pb2

class ClientRPCServicer(ClientServicer):

    def __init__(
        self, 
        subscriptions: Dict[str, Topic],
        # shutdown_flag: bool,
        # others: List[str],
    ) -> None:
        
        self._subscriptions = subscriptions
        # self._shutdown_flag = shutdown_flag
        # self._others = others

    def InformOfPublisher(
        self, 
        request: TopicDefinition, 
        context
    ) -> Client_pb2.InformConfirmation:
        
        publisher_uuid: str = request.uuid
        topic: str = request.topic_name
        message_type: str = request.message_type

        subscription = self._subscriptions.get(topic, None)

        # first, make sure we actually care about this message
        if subscription is None:
            return Client_pb2.InformConfirmation(
                return_code=1,
                status="I don't think I asked for this."
            )
        # and message type is correct
        if subscription.message_type != message_type:
            return Client_pb2.InformConfirmation(
                return_code=2,
                status=f"Unexpected message type {message_type}, expected {subscription.message_type}"
            )

        subscription.publishers.append(publisher_uuid)
        return Client_pb2.InformConfirmation(
            return_code=0,
        )
    
    # def InformOfShutdown(self, request, context):
    #     pass