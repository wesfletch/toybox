#!/usr/bin/env python3

from concurrent import futures
import grpc
from queue import Queue
import random
import unittest

from toybox_core.rpc.topic import TopicRPCServicer
from toybox_msgs.core.Test_pb2 import TestMessage
from toybox_msgs.core.Null_pb2 import Null
from toybox_core.topic import Topic
from toybox_core.client import Client
from toybox_msgs.core.Topic_pb2 import AdvertiseRequest, Confirmation, SubscriptionRequest, SubscriptionResponse, TopicDefinition
from toybox_msgs.core.Topic_pb2_grpc import add_TopicServicer_to_server, TopicStub

class Test_TopicServicer_Standalone(unittest.TestCase):
    
    def setUp(self):

        self.server = grpc.server(futures.ThreadPoolExecutor(max_workers=1))
        self.port = 50505
        self.host = "localhost"

        self.topics: dict[str,Topic] = {}
        self.clients: dict[str,Client] = {}
        self.announcements: Queue[tuple[str,str]] = Queue()

        self.topic_servicer: TopicRPCServicer = TopicRPCServicer(
            topics=self.topics,
            clients=self.clients,
            announcements=self.announcements)
        
        add_TopicServicer_to_server(servicer=self.topic_servicer, server=self.server)
        self.server.add_insecure_port(f'{self.host}:{self.port}')
        self.server.start()

        self.channel: grpc.insecure_channel = grpc.insecure_channel(f'{self.host}:{self.port}')
        self.stub = TopicStub(self.channel)

    def tearDown(self):
        self.server.stop(None)

    def test_advertise(self) -> None:

        req: AdvertiseRequest = AdvertiseRequest()
        req.publisher.publisher_id = "test"
        req.publisher.publisher_host = self.host
        req.publisher.topic_port = self.port + random.randint(1, 1000)
        req.topic_def.topic_name = "/test"
        req.topic_def.message_type = TestMessage.DESCRIPTOR.full_name

        response: Confirmation = self.stub.AdvertiseTopic(req)
        self.assertEqual(response.return_code, 0)

        topic: Topic | None = self.topics.get(req.topic_def.topic_name, None)
        self.assertTrue(topic is not None)
        self.assertEqual(topic.name, req.topic_def.topic_name)
        self.assertEqual(topic.message_type, req.topic_def.message_type)
        self.assertTrue(len(topic.subscribers) == 0)

    def test_multiple_advertise(self) -> None:

        req: AdvertiseRequest = AdvertiseRequest()
        req.publisher.publisher_id = "test"
        req.publisher.publisher_host = self.host
        req.publisher.topic_port = self.port + random.randint(1, 1000)
        req.topic_def.topic_name = "/test"
        req.topic_def.message_type = TestMessage.DESCRIPTOR.full_name

        response: Confirmation = self.stub.AdvertiseTopic(req)
        self.assertEqual(response.return_code, 0)

        req2: AdvertiseRequest = AdvertiseRequest()
        req2.publisher.publisher_id = "other_test"
        req2.publisher.publisher_host = self.host
        req2.publisher.topic_port = self.port + random.randint(1, 1000)
        req2.topic_def.topic_name = "/test"
        req2.topic_def.message_type = TestMessage.DESCRIPTOR.full_name

        response: Confirmation = self.stub.AdvertiseTopic(req2)
        self.assertEqual(response.return_code, 0)

        topic: Topic | None = self.topics.get(req.topic_def.topic_name, None)
        self.assertTrue(topic is not None)
        self.assertTrue(len(topic.publishers) == 2)
        self.assertTrue(topic.publishers.get(req.publisher.publisher_id, None) is not None)
        self.assertTrue(topic.publishers.get(req2.publisher.publisher_id, None) is not None)

    def test_incompatible_advertise(self) -> None:
        """
        Two advertise requests, but they're incompatible. The later request should fail.
        """

        req1: AdvertiseRequest = AdvertiseRequest()
        req1.publisher.publisher_id = "test"
        req1.publisher.publisher_host = self.host
        req1.publisher.topic_port = self.port + random.randint(1, 1000)
        req1.topic_def.topic_name = "/test"
        req1.topic_def.message_type = TestMessage.DESCRIPTOR.full_name

        response: Confirmation = self.stub.AdvertiseTopic(req1)
        self.assertEqual(response.return_code, 0)

        req2: AdvertiseRequest = AdvertiseRequest()
        req2.publisher.publisher_id = "test"
        req2.publisher.publisher_host = self.host
        req2.publisher.topic_port = self.port + random.randint(1, 1000)
        req2.topic_def.topic_name = "/test"
        # A different message type than the previous request...
        req2.topic_def.message_type = Null.DESCRIPTOR.full_name 

        # This request should fail.
        response: Confirmation = self.stub.AdvertiseTopic(req1)
        self.assertNotEqual(response.return_code, 0)
        
        # We should still have a stored topic definition, but...
        topic: Topic | None = self.topics.get(req1.topic_def.topic_name, None)
        self.assertTrue(topic is not None)
        # Only ONE publisher should be associated with it
        self.assertTrue(len(topic.publishers) == 1)

    def test_subscribe_then_advertise(self) -> None:
        """
        The case where we have a subscriber for a topic BEFORE it has been advertised.
        """
        topic_def: TopicDefinition = TopicDefinition(
            topic_name="/test",
            message_type=TestMessage.DESCRIPTOR.full_name)

        # First, we'll subscribe to our test message.
        sub: SubscriptionRequest = SubscriptionRequest()
        sub.subscriber_id = "test_sub"
        sub.topic_def.CopyFrom(topic_def)

        response: SubscriptionResponse = self.stub.SubscribeTopic(sub)
        self.assertEqual(response.conf.return_code, 0)
        self.assertTrue(len(response.publisher_list) == 0)

        # Since this is a standalone test and the ToyboxServer isn't running, we'll
        # have to manually add the subscriber as a client before we can advertise.
        self.clients[sub.subscriber_id] = Client(
            client_id=sub.subscriber_id,
            addr=self.host,
            rpc_port=self.port + random.randint(1, 1000),
            data_port=self.port + random.randint(1, 1000))

        pub: AdvertiseRequest = AdvertiseRequest()
        pub.publisher.publisher_id = "test_pub"
        pub.publisher.publisher_host = self.host
        pub.publisher.topic_port = self.port + random.randint(1, 1000)
        pub.topic_def.CopyFrom(topic_def)

        pub_response: Confirmation = self.stub.AdvertiseTopic(pub)
        self.assertEqual(pub_response.return_code, 0)

        # Make sure that the AdvertiseTopic RPC stored the info we'll need to inform the
        # Subscriber of the new topic.
        topic_announcement: tuple[str,str] = self.announcements.get()
        self.assertEqual(topic_announcement[0], pub.publisher.publisher_id)
        self.assertEqual(topic_announcement[1], topic_def.topic_name)


if __name__ == '__main__':
    unittest.main()