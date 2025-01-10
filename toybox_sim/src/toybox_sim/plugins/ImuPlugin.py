#!/usr/bin/env python3

import math
import time
from typing import ClassVar, Dict, Tuple, TYPE_CHECKING

import toybox_core as tbx

from toybox_sim.plugins.plugins import Plugin, InteroceptivePluginIF, PLUGIN_TYPE
from toybox_sim.primitives import Pose, Velocity

from toybox_msgs.state.Orientation_pb2 import Orientation2D

class ImuPlugin(Plugin, InteroceptivePluginIF):

    plugin_name: ClassVar[str] = "ImuPlugin"
    plugin_type: ClassVar[PLUGIN_TYPE] = PLUGIN_TYPE.INTEROCEPTIVE

    def __init__(
        self,
        id: str | None = None,
        owner_id: str | None = None,
        json_config: dict | None = None
    ) -> None:
        
        Plugin.__init__(self, id=id, owner_id=owner_id)
        InteroceptivePluginIF.__init__(self)

        # DEFAULTS
        self.orientation_topic: str | None

        if json_config is not None:
            self.parse_config(json_config)

        return

    @classmethod
    def from_config(
        cls, 
        json_config
    ) -> "ImuPlugin":
        return ImuPlugin(json_config=json_config)
    
    def parse_config(
        self, 
        json_dict: dict,
    ) -> None:
        
        for key,value in json_dict.items():
            match key:
                case "plugin_id":
                    self._id = value
                case "orientation_output_topic":
                    self.orientation_topic = value
                case _:
                    print(f"Unhandled key ignored, <{key}> == <{value}>")

    def initialize(
        self, 
        owner_id: str
    ) -> None:
        self._owner_id = owner_id
        
        self.node: tbx.node.Node = tbx.node.Node(
            name=f"{self.owner_id}/{self.id}",
            log_level="INFO",
            autostart=True)

        self.orientation_topic = self.orientation_topic if self.orientation_topic else \
            f"{self.owner_id}/imu/orientation"
        self.orientation_pub: tbx.Publisher = self.node.advertise(
            topic_name=self.orientation_topic,
            message_type=Orientation2D)
    
    def call(self) -> None:
        if self.context is None:
            return
        
        # Get the current absolute position of our owner from the sim
        current_pose: Pose | None = self.context.get_entity_pose(entity_name=self._owner_id)
        if current_pose is None:
            raise Exception(f"Our owner <{self._owner_id}> doesn't have a pose?????")
        
        orientation_msg: Orientation2D = current_pose.orientation.to_msg()
        self.orientation_pub.publish(orientation_msg)


def main() -> None:
    immy: ImuPlugin = ImuPlugin()

if __name__ == "__main__":
    main()