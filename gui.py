#!/usr/bin/env python3

from typing import Callable, List

import pyglet
import pyglet.gl as gl
from pyglet.window import mouse, key
import moderngl as mgl

pyglet.resource.path = ['resources']
pyglet.resource.reindex()

class SimWindow(pyglet.window.Window):

    def __init__(
        self,
        width: int = 800,
        height: int = 600, 
    ) -> None:
        super().__init__(
            width=width,
            height=height
        )
        self._default_grid = (10,10)
        self._grid_cell_size = 20

        self._grid: List[pyglet.shapes.ShapeBase] = []

        self._grid_batch: pyglet.graphics.Batch = pyglet.graphics.Batch()
        self.setup_grid()
        print(self._grid_batch)

    def setup_grid(self):

        self._grid.clear()

        # pixel size
        x_step: int = int(self.width / self._grid_cell_size)
        y_step: int = int(self.height / self._grid_cell_size)

        print(f'(x_step,y_step) = ({x_step},{y_step})')

        for x in range(x_step):
            for y in range(y_step):
                shape: pyglet.shapes.BorderedRectangle = pyglet.shapes.BorderedRectangle(
                    x=x*x_step,
                    y=y*y_step,
                    height=self._grid_cell_size * 2,
                    width=self._grid_cell_size * 2,
                    color=(0,0,0),
                    border_color=(100,100,100),
                    batch=self._grid_batch
                )     
                self._grid.append(shape)      
                y += 1
            x += 1

    def on_mouse_scroll(self, x, y, scroll_x, scroll_y):
        print("Mouse scrolled")
        
    def on_key_press(self, symbol, modifiers):
        print('A key was pressed')

    def on_mouse_press(self, x, y, button, modifiers):
        if button == mouse.LEFT:
            print('The left mouse button was pressed.')

    def on_draw(self):
        # print("on_draw")
        # self.clear()
        # self.draw_grid()
        self._grid_batch.draw()


def main():

    window: SimWindow = SimWindow()
    # label: pyglet.text.Label = pyglet.text.Label('Hello, world',
    #                       font_name='Times New Roman',
    #                       font_size=36,
    #                       x=window.   width//2, y=window.height//2,
    #                       anchor_x='center', anchor_y='center')

    # star: pyglet.resource.image = pyglet.resource.image("star.png")
    # star.anchor_x = star.width // 2
    # star.anchor_y = star.height // 2
    # star_sprite: pyglet.sprite.Sprite = pyglet.sprite.Sprite(
    #     img=star,
    #     x = window.height / 2,
    #     y = window.width / 2,
    # )
    # star_sprite.scale = 0.01


    # event_logger = pyglet.window.event.WindowEventLogger()
    # window.push_handlers(event_logger)

    # ctx = mgl.create_context()
    # print(f"Default framebuffer is: {ctx.screen}")

    pyglet.app.run()

if __name__ == "__main__":
    main()
