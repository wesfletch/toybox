#!/usr/bin/env python3

from dataclasses import dataclass
from typing import Dict, List, Tuple, Union, Callable

from entity import Entity, Agent
from plugin import Plugin, DiffDrivePlugin, PLUGIN_TYPE
from primitives import Pose, Position, Orientation, Velocity
from gui import SimWindow

import file_parse

import time

@dataclass
class WorldState:
    pass


class World:

    def __init__(
        self, 
        name: str = "default",
        entities: Dict[str,Entity] = {},
        window: Union[SimWindow, None] = None
    ) -> None:
        
        self._name: str = name
        self._entities: Dict[str, Entity] = entities
        self._time: float = 0.0
        self._loop_frequency: int = 20
        
        # handle GUI if present
        self._window = window
        self._USE_GUI = True if (self._window is not None) else False
        if self._USE_GUI:
            window.load_visuals(self._entities)

    @property
    def name(self) -> str:
        return self._name
    
    @name.setter
    def name(self, new_name: str) -> None:
        self._name = new_name

    @property
    def entities(self) -> Dict[str, Entity]:
        return self._entities

    @property
    def USE_GUI(self) -> bool:
        return self._USE_GUI

    @USE_GUI.setter
    def use_gui(self, use_gui: bool) -> None:
        self._USE_GUI = use_gui

    @property
    def window(self) -> SimWindow:
        return self._window
    
    @window.setter
    def window(self, window: SimWindow) -> None:
        self._window = window
        self._USE_GUI = True
        self._window.load_visuals(self.entities)
        self._window.schedule_loop(self.step, frequency=self._loop_frequency)

    def add_entity(self, entity: Entity) -> bool:
        if entity.id in self._entities.keys():
            print(f'Entity with id <{entity.id}> already in world <{self._name}>')
            return False
        else:
            self._entities[entity.id] = entity
        
        return True

    def run(self) -> None:

        # if we're using GUI, let pyglet handle the loop
        if self._USE_GUI:
            self.window.run()
        else:
            self.loop()

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

            print(self._time)
            
    def step(self, dt: float = 0.01) -> None:

        # ripe for parallelization
        for entity in self._entities.values():
            # plugin_types: Dict[PLUGIN_TYPE, str] = entity.plugin_types
            plugin: Plugin

            for plugin in entity.plugins.values():
                if plugin.id == "DiffyDrivington":
                    plugin.set_velocity_target(1.0,3.14)
                plugin.call()

        self.update_positions()
        self._time += dt

    def update_positions(self) -> None:
        
        if not self._USE_GUI:
            return

        for entity in self._entities.values():
            if entity.id in self.window._sprite_map.keys():
                # get position in sim scale ("grid-space")
                grid_x, grid_y = self.window.get_grid_coordinates(entity.pose.position.x, 
                                                                  entity.pose.position.y)
                self.window.move_sprite(id=entity.id,
                                        x=grid_x,
                                        y=grid_y)


    # FUNCTIONS TO BE CALLED BY ENTITIES
    # def move(
    #     self,
    #     motion_model: Callable[[Velocity, Pose], 
    #                             Tuple[float,float,float]],
    # )

def main():
    
    sim_window: SimWindow = SimWindow()

    worldy: World = file_parse.parse_world_file("base_config.json")
    # worldy.window = sim_window
    # worldy.window.run()
    worldy.run()


if __name__ == "__main__":
    main()