#!/usr/bin/env python3

import math
import time
from typing import Dict, Tuple, TYPE_CHECKING

import toybox_core as tbx

from toybox_sim.plugins.plugins import Plugin, BaseControlPluginIF, PLUGIN_TYPE
from toybox_sim.primitives import Pose, Velocity

from toybox_msgs.core.Test_pb2 import TestMessage
from toybox_msgs.state.Velocity_pb2 import Velocity as VelocityMsg
from toybox_msgs.primitive.Float_pb2 import Float as FloatMsg


class DiffDrivePlugin(Plugin, BaseControlPluginIF):

    plugin_name: str = "DiffDrivePlugin"
    plugin_type: PLUGIN_TYPE = PLUGIN_TYPE.BASE_CONTROL

    def __init__(
        self,
        id: str | None = None,
        owner_id: str | None = None,
        json_config: Dict[str,str] | None = None
    ) -> None:
        
        Plugin.__init__(self, id=id, owner_id=owner_id)
        BaseControlPluginIF.__init__(self)
        
        # wheel constants
        self._wheel_base = 0.1
        self._wheel_radius = 0.05
        
        # velocity parameters
        self._vel_target: Velocity = Velocity()
        self._vel_target_timeout: float = 1.0
        self._use_target_timeout: bool = True

        # timing
        self._time_last_call: float = -1.0
        self._time_last_target: float = -1.0

        # override defaults if config file provided
        if json_config is not None:
            self.parse_config(json_config)
    
    @property
    def plugin_type(self) -> PLUGIN_TYPE:
        return PLUGIN_TYPE.BASE_CONTROL

    @classmethod
    def from_config(
        cls,
        json_config: dict[str,str]
    ) -> Plugin:
        return DiffDrivePlugin(json_config=json_config)

    def parse_config(
        self,
        json_dict: dict[str,str]
    ) -> None:

        for key, value in json_dict.items():
            match key:
                case "plugin_id":
                    self._id = value
                case "wheel_radius":
                    wheel_radius: float = float(value)
                    # needs some asserts, eventually
                    self._wheel_radius = wheel_radius
                case "wheel_base":
                    wheel_base: float = float(value)
                    # needs some asserts, eventually
                    self._wheel_base = wheel_base
                case "min_accel_x":
                    min_accel_x: float = float(value)
                    # needs some asserts, eventually
                    self._min_accel_x = min_accel_x
                case "max_accel_x":
                    max_accel_x: float = float(value)
                    # needs some asserts, eventually
                    self._max_accel_x = max_accel_x
                case "min_accel_theta":
                    min_accel_theta: float = float(value)
                    # needs some asserts, eventually
                    self._min_accel_theta = min_accel_theta
                case "max_accel_theta":
                    max_accel_theta: float = float(value)
                    # needs some asserts, eventually
                    self._max_accel_theta = max_accel_theta
                case "use_vel_target_timeout":
                    self._use_target_timeout = bool(value)
                case "vel_target_timeout":
                    vel_target_timeout: float = float(value)
                    # needs some asserts, eventually
                    self._vel_target_timeout = vel_target_timeout
                case _:
                    print(f"Unhandled key ignored: <{key}> == <{value}>")

    def initialize(
        self,
        owner_id: str
    ) -> None:
        """
        """

        self._owner_id = owner_id
        print(f'Plugin <{self._id}> initialized for Entity <{self.owner_id}>')

        # TBX config
        self._node: tbx.node.Node = tbx.node.Node(
            name=f"{self.owner_id}/{self.id}",
            log_level="DEBUG",
            autostart=True)
        
        if not self._node.ready:
            raise Exception

        vel_pub_topic: str = f"/{self.owner_id}/{self.id}/velocity"
        self._node.log("DEBUG", f"Publishing velocity on: {vel_pub_topic}")
        self._vel_pub: tbx.Publisher = self._node.advertise(
            topic_name=vel_pub_topic,
            message_type=VelocityMsg)
        self._left_wheel_vel_pub: tbx.Publisher = self._node.advertise(
            topic_name=f"/{self.owner_id}/{self.id}/left_wheel",
            message_type=FloatMsg)
        self._right_wheel_vel_pub: tbx.Publisher = self._node.advertise(
            topic_name=f"/{self.owner_id}/{self.id}/right_wheel",
            message_type=FloatMsg)
        
        cmd_vel_sub_topic: str = f"/{self.owner_id}/{self.id}/cmd_vel"
        self._node.log("DEBUG", f"Subscribing to command velocity on: {cmd_vel_sub_topic}")
        self._node.subscribe(
            topic_name=cmd_vel_sub_topic, 
            message_type=VelocityMsg,
            callback_fn=self.set_target_velocity)

    def call(
        self, 
        dt: float = 0.02,
    ) -> None:
        """
        Called by the world's simulation loop.

        Args:
            dt (float, optional): Timestep. Defaults to 0.02.
        """

        assert self.context is not None, "Context not attached"

        call_time: float = time.time()

        if self._time_last_call < 0:
            self._time_last_call = call_time

        if self._use_target_timeout:
            if (call_time - self._time_last_target) >= self._vel_target_timeout:
                print(f'Time since last velocity target update exceeds limit. Setting velocity to (0.0,0.0)')
                self.set_target_velocity(Velocity())

        self._time_last_call = call_time

        current_vel: Velocity | None = self.context.get_entity_velocity(self._owner_id)
        if current_vel is not None:
            left_vel, right_vel = self.calc_wheel_vels(current_vel)

            self._vel_pub.publish(current_vel.to_msg())
            self._left_wheel_vel_pub.publish(FloatMsg(value=left_vel))
            self._right_wheel_vel_pub.publish(FloatMsg(value=right_vel))

    def set_target_velocity(
        self,
        target_vel: Velocity | VelocityMsg,
        timeout: bool = True
    ) -> None:
        """
        _summary_

        Args:
            x_vel (float): _description_
            theta_vel (float): _description_
        """
        if isinstance(target_vel, VelocityMsg):
            self._vel_target = Velocity.from_msg(target_vel)
        else:
            self._vel_target = target_vel

        self._use_target_timeout = timeout
        self._time_last_target = time.time()

    def get_target_velocity(self) -> Tuple[float,float]:
        return self._vel_target

    def calc_wheel_vels(
        self,
        vel: Velocity,
    ) -> tuple[float, float]:
        """
        Decomposes a desired target velocity [x, theta] into L- and R-wheel velocities
        """

        R: float = self._wheel_radius
        W: float = self._wheel_base

        v_l: float = ((2.0 * vel.linear.x) - (vel.angular.z * W)) / (2.0 * R)
        v_r: float = ((2.0 * vel.linear.x) + (vel.angular.z * W)) / (2.0 * R)

        return (v_l, v_r)

    def get_pose_change(
        self, 
        velocity: Velocity,
        current_pose: Pose,
        dt: float
    ) -> Tuple[float, float, float]:
        """
        Calculates the delta-x, delta-y, and delta-theta given a velocity.
        Assumes "unicycle model."

        Args:
            velocity (Tuple[float, float]): _description_

        Returns:
            Tuple[float, float, float]: _description_
        """
        # desired velocity
        v_x: float = velocity.linear.x
        v_theta: float = velocity.angular.z
        # current state
        theta: float = current_pose.orientation.theta

        # calculates velocity deltas
        delta_x: float = (v_x * math.cos(theta)) * dt
        delta_y: float = (v_x * math.sin(theta)) * dt
        delta_theta: float = v_theta * dt

        return (delta_x, delta_y, delta_theta)
