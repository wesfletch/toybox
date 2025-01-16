#!/usr/bin/env python3

import time

from toybox_core import Publisher
from toybox_core.launch import launch
from toybox_core.launchable import Launchable
from toybox_core.node import Node

from toybox_msgs.state.Velocity_pb2 import Velocity as VelocityMsg
from toybox_msgs.state.Orientation_pb2 import Orientation2D as OrientationMsg


class DiffDriver(Launchable):

    def __init__(
        self, 
        name: str
    ) -> None:
        
        self._name: str = name
        self._node: Node = Node(
            name=self._name,
            log_level="INFO",
            autostart=False)
        
        self._vehicle_name: str = "testy"
        self._topic_cmd_vel: str = f"/{self._vehicle_name}/DiffyDrivington2/cmd_vel"
        self._topic_imu_in: str = f"/{self._vehicle_name}/imu"

        self._cmd_vel_publisher: Publisher | None

    def pre_launch(self) -> bool:

        self._node.start()

        self._cmd_vel_publisher = self._node.advertise(
            topic_name=self._topic_cmd_vel, 
            message_type=VelocityMsg)
        if self._cmd_vel_publisher is None:
            return False
        
        self._node.subscribe(
            topic_name=self._topic_imu_in, 
            message_type=OrientationMsg, 
            callback_fn=self.imu_callback)

        # TODO: something like this????
        # self._node.declare_param(required=True,)
        return True
    
    def launch(self) -> bool:

        loop_freq: int = 30 
        while not self._node.is_shutdown():
            
            msg: VelocityMsg = VelocityMsg()
            msg.linear.x = 0.0
            msg.angular.z = 3.14

            self._cmd_vel_publisher.publish(msg)

            time.sleep(1 / loop_freq)

        return True

    def post_launch(self) -> bool:
        return True

    def shutdown(self):
        # TODO: can I just put this in the super()? In what case do I NOT want this behavior?
        self._node.shutdown()

    def imu_callback(self, msg: OrientationMsg) -> None:
        # print(msg)
        pass


def main() -> None:

    diffy: DiffDriver = DiffDriver(name="diffy")
    launch(diffy)

if __name__ == "__main__":
    main()