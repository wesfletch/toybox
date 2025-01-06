#!/usr/bin/env python3

import math
from typing import Callable, Dict, List, Tuple, Set

import pyglet
from pyglet.window import mouse, key

from toybox_sim.entity import Entity
from toybox_sim.ply_parse import parse, PlyModel, PlyElement, PlyProperty, ParseError

pyglet.resource.path = ["/home/wfletcher/toybox/toybox_sim/resources/"]
pyglet.resource.reindex()

PIXELS_PER_METER: int = 40
RADIANS_TO_DEGREES: float = 180 / math.pi

class SimWindow(pyglet.window.Window):

    def __init__(
        self,
        width: int = 800,
        height: int = 600,
    ) -> None:
        
        super().__init__(
            width=width,
            height=height,
            resizable=True
        )

        self._entities: Dict[str,Entity] = {} 

        self._grid_origin: Tuple[int,int] = (width//2, height//2)

        self._grid_cell_size = PIXELS_PER_METER * 1
        self._grid: Set[pyglet.shapes.ShapeBase] = set()
        self._grid_batch: pyglet.graphics.Batch = pyglet.graphics.Batch()
        self.setup_grid()

        self._polygon_batch: pyglet.graphics.Batch = pyglet.graphics.Batch()
        self._polygon_map: Dict[str, pyglet.shapes.Polygon] = {}

        self._sprite_batch: pyglet.graphics.Batch = pyglet.graphics.Batch()
        self._sprite_map: Dict[str, pyglet.sprite.Sprite] = {}

    def load_visuals(self, entities: Dict[str,Entity]) -> None:
        """
        Loads the visual representations of entities into dict.
        """

        for key in entities:
            entity: Entity = entities[key]

            if entity.model is not None:

                # Attempt to parse the .ply model
                try:
                    model: PlyModel = parse(pyglet.resource.path[0] + "/" + entity.model)
                except ParseError as e:
                    raise Exception("Failed to load model")
                
                # Extract vertices from the PlyModel to be used for constructing the
                # OpenGL shape that represents the model.
                vertices_element: PlyElement | None = model.get_element("vertex")
                if vertices_element is None:
                    print(f"Entity model is missing vertices: {entity.id}")
                    continue
                
                # Extract the color information from the model, iff it exists.
                color: Tuple[int,int,int] = (100,100,100)
                color_element: PlyElement | None = model.get_element("color")
                if color_element is not None:
                    color = color_element.data[0]

                # Generate the GL shape that will represent the model using the 
                # vertices and (optional) color from the .ply file.
                model_poly: pyglet.shapes.Polygon = pyglet.shapes.Polygon(
                    *[(PIXELS_PER_METER * x[0], PIXELS_PER_METER * x[1]) for x in vertices_element.data],
                    color=color,
                    batch=self._polygon_batch,
                )

                # Get the center of the object described by the vertices and set it as the anchor,
                # so that the center point of the model is in the middle of it, rather than
                # the lower left corner
                x_coords: List[float] = [vertex[0] for vertex in vertices_element.data]
                y_coords: List[float] = [vertex[1] for vertex in vertices_element.data]
                center_x = PIXELS_PER_METER * ((max(x_coords) - min(x_coords)) / 2)
                center_y = PIXELS_PER_METER * ((max(y_coords) - min(y_coords)) / 2)
                model_poly.anchor_position = (center_x, center_y)

                self._polygon_map[key] = model_poly
            
            if entity.sprite is not None:
                img = pyglet.resource.image(entity.sprite)
                img.anchor_position = (img.width // 2, img.height // 2)
                sprite = pyglet.sprite.Sprite(
                    img=img,
                    x = self.height / 2,
                    y = self.width / 2,
                    batch=self._sprite_batch
                )
                sprite.scale = 0.1
                self._sprite_map[key] = sprite

    def get_grid_coordinates(self, x: float, y: float) -> Tuple[int,int]:

        pixels_x: int = self._grid_origin[0] + int(PIXELS_PER_METER * x)
        pixels_y: int = self._grid_origin[1] + int(PIXELS_PER_METER * y)

        return pixels_x, pixels_y
    
    def run(self) -> None:
        pyglet.app.run()

    def schedule_loop(self, function: Callable, frequency: int = 50) -> None:
        pyglet.clock.schedule_interval(function, 1/frequency)

    def setup_grid(self):

        # Dump the old grid shapes so we can re-generate them.
        self._grid.clear()
        self._grid_batch.invalidate()

        for x in range(0, self.width, self._grid_cell_size):
            for y in range(0, self.height, self._grid_cell_size):
                vert: pyglet.shapes.Line = pyglet.shapes.Line(x, 0, x, self.height, color=(100,100,100), batch=self._grid_batch)
                horiz: pyglet.shapes.Line = pyglet.shapes.Line(0, y, self.width, y, color=(100,100,100), batch=self._grid_batch)

                # Store the shapes so they don't fall out of scope before we can draw them.
                self._grid.add(vert)
                self._grid.add(horiz)

        self._grid_origin = (self.width//2, self.height//2)

        origin_dot: pyglet.shapes.Circle = pyglet.shapes.Circle(
            x=self._grid_origin[0], y=self._grid_origin[1], radius=2.0,
            color=(255,0,0), batch=self._grid_batch)
        
        self._grid.add(origin_dot)

    def on_mouse_scroll(self, x, y, scroll_x, scroll_y):
        print("Mouse scrolled")
        
    def on_key_press(self, symbol, modifiers):
        print('A key was pressed')

    def on_mouse_press(self, x, y, button, modifiers):
        if button == mouse.LEFT:
            print('The left mouse button was pressed.')

    def on_resize(self, width, height) -> None:
        super().on_resize(width, height)

        self.setup_grid()

    def on_show(self) -> None:
        self.setup_grid()

    def on_hide(self) -> None:
        print("on_hide")

    def on_activate(self) -> None:
        self.setup_grid()

    def on_deactivate(self) -> None:
        print("on_deactivate")

    def on_draw(self):
        
        self.clear()

        self._grid_batch.draw()
        
        # Update the visual position of all entities
        for id in self._entities:
            entity: Entity = self._entities[id]

            new_position: Tuple[int,int] = self.get_grid_coordinates(
                entity.pose.position.x, entity.pose.position.y)

            if id in self._polygon_map:
                polygon: pyglet.shapes.Polygon = self._polygon_map[id]
                polygon.position = new_position
                polygon.rotation = -1 * entity.pose.orientation.theta * RADIANS_TO_DEGREES

            if id in self._sprite_map:
                sprite: pyglet.sprite.Sprite = self._sprite_map[id]
                sprite.position = (new_position[0], new_position[1], 0)

        # self._sprite_batch.draw()

        self._polygon_batch.draw()

    @property
    def entities(self) -> Dict[str, Entity]:
        return self._entities

    @entities.setter
    def entities(self, new_entities: Dict[str,Entity]) -> None:
        self._entities = new_entities

def main():

    window: SimWindow = SimWindow()
    pyglet.app.run()

if __name__ == "__main__":
    main()
