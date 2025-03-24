#!/usr/bin/env python3

import math
from typing import NamedTuple
from collections import namedtuple
import random
import pyglet


from toybox_sim.plugins.plugins import Plugin, PLUGIN_TYPE, ExteroceptivePluginIF
from toybox_sim.primitives import Pose

Laser = namedtuple('Laser', ['theta', 'range'])

# Attempting to follow Probabilistic Robotics, Ch. 6.3 "Beam Models of Range Finders"
class LaserSensorPlugin(Plugin, ExteroceptivePluginIF):

    plugin_name: str = "LaserSensorPlugin"
    plugin_type: PLUGIN_TYPE = PLUGIN_TYPE.EXTEROCEPTIVE

    def __init__(
        self, 
        id: str | None = None, 
        owner_id: str | None = None, 
        json_config: dict | None = None,
        range_meters: float | None = None,
        num_of_lasers: int = 1,
        fov_start_angle: float = 0,
        fov_end_angle: float = 360,
    ) -> None:
        
        Plugin.__init__(self, id=id, owner_id=owner_id)
        ExteroceptivePluginIF.__init__(self)

        self.range_meters: float = range_meters if range_meters else 5.0

        self._num_of_lasers = num_of_lasers
        self._fov_start_angle = fov_start_angle
        self._fov_end_angle = fov_end_angle
        
        # Visualization
        self._ray_batch: pyglet.graphics.Batch = pyglet.graphics.Batch()
        self._rays: set[pyglet.shapes.Line] = set()

        # Intrinsic params (theta)
        # TODO: These intrinsics are un-tuned. Need to get some actual data and/or implement the
        # tuning algo in Ch. 6.3.2 "Adjusting Intrinsic Parameters"
        self.measurement_intrinsic_noise: float = 0.5 # sigma_hit
        self.unexpected_object_intrinsic_noise: float = 0.5 # lambda_short

        # Intrinsic "Mixing" parameters determine the weights of our weighted average 
        # for noise measurements.
        self.z_hit: float = 0.25
        self.z_short: float = 0.25
        self.z_max: float = 0.25
        self.z_rand: float = 0.25
        assert self.z_hit + self.z_short + self.z_max + self.z_rand == 1.0

        # override defaults if config file provided
        if json_config is not None:
            self.parse_config(json_config)

    @classmethod
    def from_config(cls, json_config) -> "LaserSensorPlugin":
        return LaserSensorPlugin(json_config=json_config)
    
    def parse_config(self, json_dict):

        for key,value in json_dict.items():
            match key:
                case "plugin_id":
                    self._id = value
                case "number_of_lasers":
                    # Value must be either ODD or divisible by three
                    assert (value % 2 != 0) or (value % 3 == 0), f"number_of_lasers: <{value}>, This value needs to be odd so I can make a slice-of-a-circle out of it!"
                    self._num_of_lasers = value
                case "fov_start_angle": # degrees
                    self._fov_start_angle = value
                case "fov_end_angle":   # degrees
                    self._fov_end_angle = value
                case _:
                    print(f"Unhandled key ignored, <{key}> == <{value}>")

    def initialize(self, owner_id: str) -> None:
        self._owner_id = owner_id

        fov: float = abs((self._fov_end_angle - self._fov_start_angle) * (math.pi / 180)) # radians
        fov_start_radians: float = self._fov_start_angle * (math.pi / 180)
        fov_end_radians: float = self._fov_end_angle * (math.pi / 180)
        print(f"fov=={fov}, (start, end)=={(fov_start_radians, fov_end_radians)}")

        thetas: list[int] = []
        
        # The first laser is always at the middle of the FOV
        midpoint: float = min(fov_start_radians, fov_end_radians) + (fov / 2)
        midpoint_index: int = self._num_of_lasers - 1
        thetas.append(midpoint)

        # The distance between two lasers
        slice: float = fov / (self._num_of_lasers - 1)

        x: int = 1
        for y in range(1, self._num_of_lasers):
            if y == midpoint_index:
                continue
            if y % 2 != 0:
                theta: float = midpoint - (slice * x)
            else:
                theta: float = midpoint + (slice * x)
                x += 1

            thetas.append(theta)
        
        # print(f"thetas=={[theta * (180 / math.pi) for theta in thetas]}")
        
        self._lasers: list[Laser] = [Laser(theta=theta, range=0) for theta in thetas]

    def call(self) -> None:
        return None

    def visualize(self) -> None:
        
        scale: int = self.window_context.get_window_pixels_per_meter()
        max_ray_length: float = self.range_meters * scale

        pose_of_owner: Pose | None = self.context.get_entity_pose(self.owner_id)
        if pose_of_owner is None:
            return

        x1, y1 = self.window_context.get_window_grid_coords(
            x=pose_of_owner.position.x,
            y=pose_of_owner.position.y)

        # TODO: it'd be nice if we only re-calculated everything when the sensor had
        # actually moved/rotated. For now, it's no big deal.
        self._ray_batch.invalidate()
        self._rays.clear()
        
        for laser in self._lasers:
            theta: float = pose_of_owner.orientation.theta + laser.theta

            # Calculate the endpoint of the ray
            x2_m = pose_of_owner.position.x + max_ray_length * math.cos(theta) # L * cos(theta)
            y2_m = pose_of_owner.position.y + max_ray_length * math.sin(theta) # L * sin(theta)
            x2, y2 = self.window_context.get_window_grid_coords(x2_m, y2_m)

            # Store the ray so it doesn't go out of scope.
            self._rays.add(pyglet.shapes.Line(
                x=x1, 
                y=y1,
                x2=x2,
                y2=y2,
                color=(255,0,0),
                thickness=5,
                batch=self._ray_batch))
        
        # TODO: Alternatively, I could RETURN this batch and let the GUI handle
        # when it's drawn/invalidated.... Things to think about.
        self._ray_batch.draw()

    def _range(self) -> None:
        # TODO: Here's where I actually need to raycast
        for laser in self._lasers:
            pass

    def _apply_noise(
        self,
        true_range: float, # z(^k*)(_t)
    ) -> float:
        
        # Types of noise:
        # 1) measurement noise: UNIVARIATE NORMAL DISTN
        p_hit: float = self._apply_measurement_noise(true_range=true_range)

        # 2) errors due to unexpected objects: EXPONENTIAL DISTN
        p_short: float = self._apply_unexpected_object_noise(true_range=true_range)

        # 3) errors due to failure to detect objects: POINT MASS DISTN
        # When laser sensors fail to detect anything, they typically return the max value
        p_max: float = self._apply_failure_noise(true_range=true_range)

        # 4) Random, unexplained noise: UNIFORM DISTN OVER FULL DOMAIN
        p_rand: float = self._apply_random_noise(true_range=true_range)

        print((p_hit, p_short, p_max, p_rand))

        p: float = \
            self.z_hit * p_hit + \
            self.z_short * p_short + \
            self.z_max * p_max + \
            self.z_rand * p_rand

        return p

    def _apply_measurement_noise(self, true_range: float) -> float:
        measurement_noise: float # p_hit
        if 0 <= true_range <= self.range_meters:
            measurement_noise = random.normalvariate(
                mu=true_range, sigma=self.measurement_intrinsic_noise)
        else:
            measurement_noise = 0.0

        return measurement_noise
    
    def _apply_unexpected_object_noise(self, true_range: float) -> float:
        unexpected_object_noise: float # p_short
        if 0 <= true_range <= self.range_meters:
            unexpected_object_noise = random.expovariate(
                lambd=self.unexpected_object_intrinsic_noise)
        else:
            unexpected_object_noise = 0.0

        return unexpected_object_noise
    
    def _apply_failure_noise(self, true_range: float) -> float:

        failure_noise: float # p_max
        if true_range == self.range_meters:
            failure_noise = 1.0
        else:
            failure_noise = 0.0
        return failure_noise
    
    def _apply_random_noise(self, true_range: float) -> float:

        random_noise: float # p_rand
        if 0 <= true_range <= self.range_meters:
            random_noise = random.uniform(0, self.range_meters)
        else:
            random_noise = 0.0
        return random_noise
    

def main() -> None:
    
    laser: LaserSensorPlugin = LaserSensorPlugin(id="laser", owner_id=None)
    print(laser._apply_noise(true_range=5.0))
    print(laser._apply_noise(true_range=5.1))

if __name__ == "__main__":
    main()
