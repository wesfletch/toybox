
from typing import TYPE_CHECKING

from toybox_sim.gui import SimWindow
from toybox_sim.world import World
from toybox_sim.context import PluginContext
if TYPE_CHECKING:
    from toybox_sim.entity import Entity

class Simulation:

    def __init__(
        self, 
        name: str, 
        window: SimWindow | None = None, 
        world: World | None = None
    ) -> None:

        self._name: str = name
        
        self._world: World = world if world else World()
        self._world_context: PluginContext = PluginContext(self._world)
        for entity in self._world.entities.values():
            for plugin in entity.plugins.values():
                plugin.context = self._world_context

        self._USE_GUI: bool
        self._window: SimWindow | None = window
        if self._window is not None:
            self._USE_GUI = True
            self._window.entities = self._world.entities
            self._window.load_visuals(self._window.entities)
            self._window.schedule_loop(self._world.step, frequency=self._world._loop_frequency)
        else:
            self._USE_GUI = False
    
    def run(self) -> None:

        if self._USE_GUI:
            self._window.run()
        else:
            self._world.loop()