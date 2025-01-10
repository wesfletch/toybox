#!/usr/bin/env python3

import unittest

import concurrent.futures as futures
import grpc

import toybox_msgs.core.Client_pb2 as Client_pb2
from toybox_msgs.core.Client_pb2_grpc import ClientStub, add_ClientServicer_to_server
from toybox_core.rpc.client import ClientRPCServicer
from toybox_msgs.core.Topic_pb2 import TopicDefinition
from toybox_core.topic import Topic


class Test_ClientServicer(unittest.TestCase):

    port: int = 50505

    def setUp(self) -> None:
        
        self._subscriptions: dict[str, Topic] = {}
        self._others: list[str] = []
        
        self._server = grpc.server(
            thread_pool=futures.ThreadPoolExecutor(max_workers=10)
        )
        self._server.add_insecure_port(f'[::]:{self.port}')
        add_ClientServicer_to_server(
            server=self._server,
            servicer=ClientRPCServicer(subscriptions=self._subscriptions,
                                    #    others=self._others,
                                       )
        )
        self._server.start()

    def tearDown(self) -> None:
        self._server.stop(grace=None)

    def test_InformOfPublisher(self) -> None:

        request: TopicDefinition = TopicDefinition(
            uuid="test",
            topic_name="dummy",
            message_type="dummy",
        )

        # we've been informed of a topic we don't care about
        response: Client_pb2.InformConfirmation
        with grpc.insecure_channel(f'localhost:{self.port}') as channel:
            stub = ClientStub(channel=channel)
            response = stub.InformOfPublisher(request=request)
        self.assertEqual(response.return_code, 1)
        
        # now, we care about the topic, but the message type is wrong
        self._subscriptions['dummy'] = Topic(
            name="dummy",
            message_type="test_message_type"
        )
        with grpc.insecure_channel(f'localhost:{self.port}') as channel:
            stub = ClientStub(channel=channel)
            response = stub.InformOfPublisher(request=request)
        self.assertEqual(response.return_code, 2)

        # finally we've received a topic we care about, with the correct message type
        # modify request to contain proper message type
        request.message_type = "test_message_type"
        with grpc.insecure_channel(f'localhost:{self.port}') as channel:
            stub = ClientStub(channel=channel)
            response = stub.InformOfPublisher(request=request)
        self.assertEqual(response.return_code, 0)

        # now that we've received a good message, our subscriptions should
        # contain the uuid of the publisher
        subscription: Topic = self._subscriptions.get(request.topic_name, None)
        self.assertFalse(subscription is None)
        self.assertTrue(request.uuid in subscription.publishers)

if __name__ == '__main__':
    unittest.main()