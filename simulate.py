#!/usr/bin/env python3

from typing import Dict, List, Tuple

from entity import Entity, Agent
from plugin import Plugin, DiffDrivePlugin, PLUGIN_TYPE
from primitives import Pose, Position, Orientation

import time
import math
import json


def load_entity_config(
    filename: str,
    world: World
)

class World:

    def __init__(self, 
        name: str = "default",
    ) -> None:
        
        self._world_name: str = name
        self._entities: Dict[str, Entity] = {}
        self._time: float = 0.0 

    @property
    def entities(self) -> Dict[str, Entity]:
        return self._entities

    def add_entity(self, entity: Entity) -> bool:
        if entity.id in self._entities.keys():
            print(f'Entity with id <{entity.id}> already in world <{self._world_name}>')
            return False
        else:
            self._entities[entity.id] = entity
        
        return True

    def loop(
        self, 
        frequency: int = 1,
        timestep: float = -1
    ) -> None:
        
        loop_period: float = 1 / frequency
        dt: float = timestep if (timestep > 0) else loop_period
        start_time: float = time.time()

        while True:

            self.step(dt)
            
            # "best effort" time sync 
            time_delta: float = time.time() - start_time
            if time_delta < loop_period:
                time.sleep(loop_period - time_delta)
            start_time = time.time() 
            
    def step(self, dt: float = 0.01) -> None:
        
        # ripe for parallelization
        for entity in self._entities.values():

            plugin_types: Dict[PLUGIN_TYPE, str] = entity.plugin_types
            plugin: Plugin

            for plugin in entity.plugins.values():
                plugin.call()

            print(entity.pose)

        self._time += dt

    # not handling orientation properly yet
    # def move_entity(
    #     self,
    #     entity: 'Entity',
    #     delta_pos: Tuple[float, float, float]
    # ) -> None:

    #     # current_pose: Pose = entity.pose

    #     # x: float = current_pose.position.x + delta_pos[0]
    #     # y: float = current_pose.position.y + delta_pos[1]
    #     # theta: float = (current_pose.orientation.theta + delta_pos[2]) % (2*math.pi)

    #     # entity.pose = Pose(
    #     #     position=Position(x=x, y=y),
    #     #     orientation=Orientation(theta=theta)
    #     # )

    #     entity.pose.update(delta_p=delta_pos)


def main():

    worldy: World = World()
    agenty: Agent = Agent(
        id="test",
        position=(0.0,0.0,(3/2)*math.pi)
    )
    worldy.add_entity(agenty)

    diffy = DiffDrivePlugin("diffy")
    agenty.load_plugin("diffy", diffy)
    diffy.set_velocity_target(1.0, 0.1, timeout=False)

    print(agenty.get_plugin('diffy').plugin_name)

    worldy.loop(frequency=20)

if __name__ == "__main__":
    main()