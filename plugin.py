#!/usr/bin/env python3

from abc import ABC, abstractmethod, abstractproperty
from typing import Any, Dict, Tuple
import math
from enum import Enum
import time
import json, os

from primitives import Pose

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from entity import Entity

class PluginNotFoundException(Exception):
    """Exception raised when a plugin cannot be found. 

    Args:
        plugin_id (str): the name of the plugin that couldn't be found
        object_id (str, optional): The name of the object that was searched for the plugin. Defaults to "".
    """
    def __init__(self, plugin_id: str, object_id: str = ""):
        self.message = f'No plugin \'{plugin_id}\' found for object \'{object_id}\''
        super().__init__(self.message)

class PLUGIN_TYPE(Enum):
    MOVEMENT = 1
    BASE_CONTROL = 2

class Plugin(ABC):

    @classmethod
    @property
    @abstractmethod
    def plugin_name(cls) -> str:
        raise NotImplementedError

    @classmethod
    @property
    @abstractmethod
    def plugin_type(cls) -> PLUGIN_TYPE:
        raise NotImplementedError

    @abstractmethod
    def initialize(self, owner: 'Entity') -> None:
        raise NotImplementedError

    @abstractmethod
    def call(self) -> Any:
        raise NotImplementedError

class DiffDrivePlugin(Plugin):

    plugin_name: str = "DiffDrivePlugin"
    plugin_type: PLUGIN_TYPE = PLUGIN_TYPE.BASE_CONTROL

    def __init__(
        self,
        id: str,
        config_file: str = None
    ) -> None:
        
        self._id: str = id

        if config_file:
            raise NotImplementedError
        else:
            self._wheel_base = 0.1
            self._wheel_radius = 0.05

        self._owner: 'Entity'
        self._vel_target: Tuple[float, float] = (0,0)
        self._vel_target_timeout: float = 1.0
        self._use_target_timeout: bool = True

        # timing
        self._time_last_call: float = -1.0
        self._time_last_target: float = -1.0

    @classmethod
    def create_from_json(
        cls, 
        json_dict: Dict[str,str]
    ) -> 'DiffDrivePlugin':

        self: DiffDrivePlugin = cls.__new__(cls)
        # ddp: DiffDrivePlugin = DiffDrivePlugin()

        if "wheel_radius" in json_dict:
            wheel_radius: float = float(json_dict["wheel_radius"])
            # needs some asserts, eventually
            self._wheel_radius = wheel_radius
        if "wheel_base" in json_dict:
            wheel_base: float = float(json_dict["wheel_base"])
            # needs some asserts, eventually
            self._wheel_base = wheel_base
        # if "min_accel_x" in json_dict:
        #     min_accel_x: float = float(json_dict["min_accel_x"])
        #     # needs some asserts, eventually
        #     self._min_accel_x = min_accel_x
        # if "max_accel_x" in json_dict:
        #     max_accel_x: float = float(json_dict["max_accel_x"])
        #     # needs some asserts, eventually
        #     self._max_accel_x = max_accel_x
        # if "min_accel_theta" in json_dict:
        #     min_accel_theta: float = float(json_dict["min_accel_theta"])
        #     # needs some asserts, eventually
        #     self._min_accel_theta = min_accel_theta
        # if "max_accel_theta" in json_dict:
        #     max_accel_theta: float = float(json_dict["max_accel_theta"])
        #     # needs some asserts, eventually
        #     self._max_accel_theta = max_accel_theta
        if "vel_target_timeout" in json_dict:
            vel_target_timeout: float = float(json_dict["vel_target_timeout"])
            # needs some asserts, eventually
            self._vel_target_timeout = vel_target_timeout
            self._use_target_timeout = True
        
        return self

    def initialize(
        self,
        owner: 'Entity'
    ) -> None:
        """_summary_

        Args:
            owner (Entity): _description_
        """
        self._owner = owner
        print(f'Plugin <{self._id}> initialized for Entity <{self._owner.id}>')

    def call(
        self, 
        dt: float = 0.02,
    ) -> None:
        """
        Called by the world's simulation loop.

        Args:
            dt (float, optional): _description_. Defaults to 0.02.
            vel_target (Tuple[float, float], optional): _description_. Defaults to (0,0).
        """
        call_time: float = time.time()

        if self._time_last_call < 0:
            self._time_last_call = call_time

        if self._use_target_timeout:
            if (call_time - self._time_last_target) >= self._vel_target_timeout:
                print(f'Time since last velocity target update exceeds limit. Setting velocity to (0.0,0.0)')
                self.set_velocity_target(0.0, 0.0)
        

        delta_pos: Tuple[float, float, float] = self.calc_position_delta(
                    velocity=self._vel_target,
                    current_pose=self._owner.pose,
                    dt=dt
                )
    
        # need simulations permission for this, ultimately
        # sim.request_upate()???
        self._owner.pose.update(delta_p=delta_pos)

        self._time_last_call = call_time

    def set_velocity_target(
        self,
        x_vel: float,
        theta_vel: float,
        timeout: bool = True
    ) -> None:
        """_summary_

        Args:
            x_vel (float): _description_
            theta_vel (float): _description_
        """
        self._vel_target = (x_vel, theta_vel)
        self._use_target_timeout = timeout
        self._time_last_target = time.time()

    def calc_wheel_vels(
        self,
        x_vel: float,
        theta_vel: float
    ) -> Tuple[float, float]:
        """Decomposes a desired target velocity [x, theta] into L- and R-wheel velocities
        """

        R: float = self._wheel_radius
        W: float = self._wheel_base

        v_l: float = ((2.0 * x_vel) - (theta_vel * W)) / (2.0 * R)
        v_r: float = ((2.0 * x_vel) + (theta_vel * W)) / (2.0 * R)

        return (v_l, v_r)

    def calc_position_delta(
        self, 
        velocity: Tuple[float, float],
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
        v_x: float = velocity[0]
        v_theta: float = velocity[1]
        # current state
        x: float = current_pose.position.x
        y: float = current_pose.position.y
        theta: float = current_pose.orientation.theta

        # calculates velocity deltas
        delta_x: float = (v_x * math.cos(theta)) * dt
        delta_y: float = (v_x * math.sin(theta)) * dt
        delta_theta: float = v_theta * dt

        return (delta_x, delta_y, delta_theta)


    def load_base_config(self) -> None:
        pass


def main():

    json_file = open("base_config.json", "r")
    json_file = json.load(json_file)

    print(json_file)

    diff_drive_json = json_file['entities'][0]['plugins'][0]
    print(diff_drive_json)

    diffy: DiffDrivePlugin = DiffDrivePlugin.create_from_json(json_dict=diff_drive_json)
    print(diffy)

if __name__ == "__main__":
    main()