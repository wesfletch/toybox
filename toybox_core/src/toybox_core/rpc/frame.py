#!/usr/bin/env python3

from dataclasses import dataclass, field

import grpc

import toybox_msgs.core.Frame_pb2 as Frame_pb2
from toybox_msgs.core.Frame_pb2_grpc import TransformServicer
from toybox_msgs.state import Pose_pb2 as Pose
from toybox_msgs.primitive.Quaternion_pb2 import Quaternion
from toybox_msgs.primitive.Vector_pb2 import Vector3

@dataclass
class Frame:
    id: str
    parent: "Frame | None" = None
    children: dict[str, "Frame"] = field(default_factory=dict)
    transform: Pose.Pose = field(default_factory=Pose.Pose, init=True)


FrameName = str

class FrameTree:

    def __init__(self) -> None:
        self._root: Frame | None = None
        self._frames: dict[str, Frame] = {}

    def add_frame(self, frame: Frame) -> bool:        
        # If the frame already exists, we're good
        if self.find_frame(id=frame):
            return True

        if frame.parent is None:
            if self._root is not None:
                # Make sure that parent exists already.
                print(f"Root node already exists")
                return False
            else:
                self._root = frame
        else:
            parent: Frame = self.find_frame(id=frame.parent.id)
            assert parent is not None
            parent.children[frame.id] = frame
        
        self._frames[frame.id] = frame
        return True

    def find_frame(self, id: str, root: Frame | None = None) -> Frame | None:
        # TODO: This DFS approach isn't necessary, there's no real reason
        # not to just use the dict.
        root = self._root if root is None else root
        if root is None:
            # Tree is empty
            return None

        if root.id == id:
            return root

        for child in root.children.values():
            frame: Frame | None = self.find_frame(id=id, root=child)
            if frame is not None:
                return frame
        return None
    
    def traverse_up(self, id: str) -> list[Frame]:
        frame: Frame | None = self.find_frame(id=id)
        if frame is None:
            raise Exception(f"Frame `{id}` doesn't exist.")
        
        frames: list[Frame] = []
        while frame.parent is not None:
            frames.append(frame.parent)
            frame = frame.parent
        
        return frames
    
    @staticmethod
    def transform(reference_frame: Frame, frame: Frame,) -> Frame:

        ref_transform: Pose.Pose = reference_frame.transform

        # Translation (easy)
        transform: Pose.Pose = Pose.Pose()
        transform.position.x = ref_transform.position.x + frame.transform.position.x    
        transform.position.y = ref_transform.position.y + frame.transform.position.y
        transform.position.z = ref_transform.position.z + frame.transform.position.z
        # Rotation (hard)
        transform.orientation.CopyFrom(
            FrameTree._quat_mul(
                quat1=reference_frame.transform.orientation, 
                quat2=frame.transform.orientation,
            )
        )

        return Frame(
            id=frame.id, 
            parent=frame.parent, 
            children=frame.children, 
            transform=transform,
        )
    
    @staticmethod
    def _quat_mul(quat1: Quaternion, quat2: Quaternion) -> Quaternion:
        x1: float = quat1.x # a0
        y1: float = quat1.y # a1
        z1: float = quat1.z # a2
        w1: float = quat1.w # a3
        
        x2: float = quat2.x # b0
        y2: float = quat2.y # b1
        z2: float = quat2.z # b2
        w2: float = quat2.w # b3

        x: float = (x1 * y2) + (y1 * x2) + (z1 * w2) - (w1 * z2)
        y: float = (x1 * z2) + (z1 * x2) + (w1 * y2) - (y1 * w2)
        z: float = (x1 * w2) + (w1 * x2) + (y1 * z2) - (z1 * y2)
        w: float = (x1 * x2) - (y1 * y2) - (z1 * z2) - (w1 * w2)

        return Quaternion(x=x, y=y, z=z, w=w)

    @staticmethod
    def validate_frame_name(name: str) -> FrameName:
        pass

class FrameServicer(TransformServicer):

    def __init__(
        self, 
        root_frame_id: str | None = None,
    ) -> None:
        self._frame_tree: FrameTree = FrameTree()

        # Ensure that there's always a root at startup.
        root_frame_id = root_frame_id if root_frame_id else "root"
        if not self._frame_tree.add_frame(frame=Frame(id=root_frame_id, parent=None)):
            raise Exception("Something is deeply wrong...")

    def RegisterFrame(
        self, 
        request: Frame_pb2.RegisterFrameRequest, 
        context: grpc.ServicerContext,
    ) -> Frame_pb2.RegisterFrameResponse:

        response: Frame_pb2.RegisterFrameResponse = Frame_pb2.RegisterFrameResponse()

        parent_id: str = request.parent_id
        assert len(parent_id) != 0

        child_id: str = request.frame_id
        assert len(child_id) != 0

        # Find the parent.
        # TODO: Might be less annoying to just store parent_id in Frame, instead
        # of the reference to parent itself.
        parent_frame: Frame | None = self._frame_tree.find_frame(id=parent_id)
        if parent_frame is None:
            response.success = False
            response.status = f"Parent `{parent_id}` not found."
            return response

        frame: Frame = Frame(id=child_id, parent=parent_frame)

        result: bool = self._frame_tree.add_frame(frame)
        if not result:
            response.success = False
            response.status = f"Failed to add frame `{frame}` to tree."
            return response

        response.success = True
        response.status = "OK"
        return response

    def UpdateFrame(
        self, 
        request: Frame_pb2.UpdateFrameRequest, 
        context: grpc.ServicerContext,
    ) -> Frame_pb2.UpdateFrameResponse:
        return super().UpdateFrame(request, context)
    
    def GetRootFrame(
        self, 
        request: Frame_pb2.GetRootFrameRequest, 
        context: grpc.ServicerContext,
    ) -> Frame_pb2.GetRootFrameResponse:
        return super().GetRootFrame(request, context)

    def GetFrame(
        self, 
        request: Frame_pb2.GetFrameRequest, 
        context: grpc.ServicerContext,
    ) -> Frame_pb2.GetFrameResponse:
        return super().GetFrame(request, context)

def main() -> None:
    frame: Frame = Frame(id="framey", parent=None)
    child: Frame = Frame(id="frame_child", parent=frame, transform=Pose.Pose(
        position=Vector3(x=1,y=1,z=1),
        orientation=Quaternion(x=0, y=0, z=0, w=1)))
    child2: Frame = Frame(id="frame_child2", parent=frame)
    child2_child: Frame = Frame(id="frame_child2_child", parent=child2)

    ftree: FrameTree = FrameTree()
    ftree.add_frame(frame)
    ftree.add_frame(child)
    ftree.add_frame(child2)
    ftree.add_frame(child2_child)
    # print(ftree.find_frame(child2_child.id))
    # print(ftree.traverse_up(child2_child.id))

    print(ftree.transform(reference_frame=frame, frame=child))

if __name__ == "__main__":
    main()