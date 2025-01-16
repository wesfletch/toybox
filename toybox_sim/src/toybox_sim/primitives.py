#!/usr/bin/env python3

from dataclasses import dataclass,field
from typing import List, Tuple

from math import pi as PI

from toybox_msgs.primitive.Vector_pb2 import Vector3 as VectorMsg
from toybox_msgs.state.Position_pb2 import Position as PositionMsg
from toybox_msgs.state.Velocity_pb2 import Velocity as VelocityMsg
from toybox_msgs.state.Orientation_pb2 import Orientation2D as OrientationMsg
from toybox_msgs.state.Pose_pb2 import Pose2D as PoseMsg


@dataclass
class Vector3D:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def to_msg(self) -> VectorMsg:
        return VectorMsg(x=self.x, y=self.y, z=self.z)

@dataclass
class Velocity:
    linear: Vector3D = field(default_factory=Vector3D)
    angular: Vector3D = field(default_factory=Vector3D)
    
    def to_msg(self) -> VelocityMsg:
        return VelocityMsg(
            linear=self.linear.to_msg(), 
            angular=self.angular.to_msg())
    
    @classmethod
    def from_msg(cls, velocity_msg: VelocityMsg) -> "Velocity":
        linear: Vector3D = Vector3D(
            x=velocity_msg.linear.x, 
            y=velocity_msg.linear.y,
            z=velocity_msg.linear.z)
        angular: Vector3D = Vector3D(
            x=velocity_msg.angular.x, 
            y=velocity_msg.angular.y,
            z=velocity_msg.angular.z)
        return Velocity(linear=linear, angular=angular)
    
@dataclass
class Position:
    """
    Position in 3-space.
    """
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def to_msg(self) -> PositionMsg:
        return PositionMsg(x=self.x, y=self.y, z=self.z)

@dataclass
class Orientation:
    """
    Orientation in 2D space.
    """
    theta: float = 0.0 # radians

    def to_msg(self) -> OrientationMsg:
        return OrientationMsg(theta=self.theta) 

@dataclass
class Pose:
    position: Position = field(default_factory=Position)
    orientation: Orientation = field(default_factory=Orientation)

    def update(
        self,
        delta_p: Tuple[float,float,float]
    ) -> None:
        self.position.x = self.position.x + delta_p[0]
        self.position.y = self.position.y + delta_p[1]
        self.orientation.theta = (self.orientation.theta + delta_p[2]) % (2*PI)
    
    def to_msg(self) -> PoseMsg:
        return PoseMsg(position=self.position.to_msg(), orientation=self.orientation.to_msg())

class State:

    def __init__(self) -> None:
        pass

def main():
    
    # Just making sure all of these work
    vel: Velocity = Velocity(x=1.0,y=0.0,z=0.0)
    pos: Position = Position(x=0.1,y=0.1,z=0.1)
    ori: Orientation = Orientation(theta=3.14159)

    print(vel.to_msg())
    print(pos.to_msg())
    print(ori.to_msg())

    pose: Pose = Pose(position=pos, orientation=ori)
    print(pose.to_msg())

if __name__ == "__main__":
    main()
