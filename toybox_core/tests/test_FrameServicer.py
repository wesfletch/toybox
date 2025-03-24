#!/usr/bin/env python3

import grpc
import unittest
from concurrent import futures

import toybox_msgs.core.Frame_pb2 as Frame_pb2
from toybox_msgs.core.Frame_pb2_grpc import TransformServicer, add_TransformServicer_to_server, TransformStub
from toybox_msgs.state import Pose_pb2 as Pose
from toybox_msgs.primitive.Quaternion_pb2 import Quaternion
from toybox_msgs.primitive.Vector_pb2 import Vector3

# TODO: move the frame stuff out of RPC
from toybox_core.rpc.frame import FrameServicer, Frame, FrameTree

class Test_FrameServicer(unittest.TestCase):
    
    def setUp(self) -> None:

        self.server: grpc.Server = grpc.server(
            futures.ThreadPoolExecutor(max_workers=1)
        )
        self.port: int = 50505
        self.host: str = "localhost"
        self.addr: str = f"{self.host}:{self.port}"

        self.root_frame_id: str = "world"
        self.frame_servicer: FrameServicer = FrameServicer(root_frame_id=self.root_frame_id)
        add_TransformServicer_to_server(
            servicer=self.frame_servicer, 
            server=self.server
        )
        self.server.add_insecure_port(self.addr)
        self.server.start()

        self.channel = grpc.insecure_channel(self.addr)
        self.stub: TransformStub = TransformStub(self.channel)

    def tearDown(self) -> None:
        self.server.stop(None)

    def test_GetRootFrameRPC(self) -> None:

        pass

    def test_RegisterFrameRPC(self) -> None:

        req: Frame_pb2.RegisterFrameRequest = Frame_pb2.RegisterFrameRequest()
        
        # Create frame ${root}->parent
        req.parent_id = self.root_frame_id
        req.frame_id = "parent"
        response: Frame_pb2.RegisterFrameResponse = self.stub.RegisterFrame(req)
        self.assertTrue(response.success, response.status)

        # Create the frame parent->child
        req.parent_id = req.frame_id
        req.frame_id = "child"
        response = self.stub.RegisterFrame(req)
        self.assertTrue(response.success, response.status)

        # Create a second child of parent parent->child2
        req.frame_id = "child2"
        response = self.stub.RegisterFrame(req)
        self.assertTrue(response.success, response.status)

        # Register a frame that already exists (which is fine)
        response = self.stub.RegisterFrame(req)
        self.assertTrue(response.success, response.status)

        # Do something wrong: register a frame whose parent doesn't exist
        req.parent_id = "DOESNOTEXIST"
        response = self.stub.RegisterFrame(req)
        self.assertFalse(response.success, response.status)

if __name__ == '__main__':
    unittest.main()