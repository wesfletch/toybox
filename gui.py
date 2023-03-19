#!/usr/bin/env python3

import pyglet
from pyglet.window import mouse, key
import moderngl as mgl

pyglet.resource.path = ['resources']
pyglet.resource.reindex()

def main():
    window: pyglet.window.Window = pyglet.window.Window(
        width=800,
        height=600,
    )
    label: pyglet.text.Label = pyglet.text.Label('Hello, world',
                          font_name='Times New Roman',
                          font_size=36,
                          x=window.width//2, y=window.height//2,
                          anchor_x='center', anchor_y='center')

    star: pyglet.resource.image = pyglet.resource.image("star.png")
    star.anchor_x = star.width // 2
    star.anchor_y = star.height // 2
    star_sprite: pyglet.sprite.Sprite = pyglet.sprite.Sprite(
        img=star,
        x = window.height / 2,
        y = window.width / 2,
    )
    star_sprite.scale = 0.01

    @window.event
    def on_key_press(symbol, modifiers):
        print('A key was pressed')

    @window.event
    def on_mouse_press(x, y, button, modifiers):
        if button == mouse.LEFT:
            print('The left mouse button was pressed.')

    @window.event
    def on_draw():
        window.clear()
        label.draw()
        star_sprite.draw()

    event_logger = pyglet.window.event.WindowEventLogger()
    window.push_handlers(event_logger)

    ctx = mgl.create_context()
    print(f"Default framebuffer is: {ctx.screen}")

    pyglet.app.run()

if __name__ == "__main__":
    main()
