#!/usr/bin/env python3

from toybox_core.launch import Launchable
from toybox_sim.context import PluginContext, WindowContext
from toybox_sim.file_parse import parse_world_file
from toybox_sim.gui import SimWindow
from toybox_sim.world import World

class Simulation(Launchable):

    def __init__(
        self, 
        name: str = "simulation", 
        use_gui: bool = True, 
        world: str | None = None
    ) -> None:

        self._name: str = name
        
        self._world: World = parse_world_file(world) if world is not None else World()
        self._world_context: PluginContext = PluginContext(self._world)

        self._shutdown: bool = False

        self._USE_GUI: bool = use_gui
        self._window: SimWindow | None = None
        self._window_context: WindowContext | None = None
        if self._USE_GUI:
            self._window = SimWindow()
            self._window.entities = self._world.entities
            self._window.load_visuals(self._window.entities)
            self._window.schedule_loop(self._world.step, frequency=self._world._loop_frequency)
            self._window_context = WindowContext(self._window)

        # Attach the World and Window to all plugins
        for entity in self._world.entities.values():
            for plugin in entity.plugins.values():
                plugin.context = self._world_context
                if self._window_context is not None:
                    plugin.window_context = self._window_context
    
    def run(self) -> None:

        self._world.initialize()

        if self._USE_GUI:
            self._window.run()
        else:
            self._world.loop()

    def launch(self) -> bool:
        self.run()
        return True

    def shutdown(self) -> None:
        self._world.trigger_shutdown()
        if self._window:
            self._window.trigger_shutdown()
        self._shutdown = True
