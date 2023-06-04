#!/usr/bin/env python3

from typing import Callable, Dict, List, Tuple

import pyglet
import pyglet.gl as pgl
from pyglet.math import Vec2
from pyglet.graphics.shader import Shader, ShaderProgram
from pyglet.graphics.vertexdomain import VertexList, IndexedVertexList
from pyglet.window import mouse, key

import moderngl as mgl

from entity import Entity

pyglet.resource.path = ['resources']
pyglet.resource.reindex()

class ScreenAttributeGroup(pyglet.graphics.Group):
    def __init__(
        self,
        shader_program: ShaderProgram,
        screen_size: Vec2,
        grid_cell_size: int,
    ) -> None:
        super().__init__()
        self.program: ShaderProgram = shader_program
        self._screen_size: Vec2 = screen_size
        self._tile_size: int = grid_cell_size
        
    @property
    def screen_size(self) -> Vec2: return self._screen_size

    @screen_size.setter
    def screen_size(self, width: int, height: int) -> None:
        self._screen_size = Vec2(x=width, y=height)

    @property
    def tile_size(self) -> int: return self._tile_size

    @tile_size.setter
    def tile_size(self, new_tile_size: int) -> None:
        self._tile_size = new_tile_size

    def set_state(self) -> None:
        self.program.use()
        # set uniforms
        self.program.uniforms['screenSize'] = self._screen_size
        self.program.uniforms['tileSize'] = self._tile_size

    def unset_state(self) -> None:
        self.program.stop()


class SimWindow(pyglet.window.Window):

    def __init__(
        self,
        width: int = 800,
        height: int = 600,
        # entities: Dict[str,Entity] = {}
    ) -> None:
        
        super().__init__(
            width=width,
            height=height,
            resizable=True
        )

        # for now, don't update this on resize. Maybe later there can
        #   be some sort of recenter button
        self._grid_origin: Tuple[int,int] = (width//2, height//2)

        # self._default_grid = (10,10)
        self._grid_cell_size = 20
        self._grid: List[pyglet.shapes.ShapeBase] = []
        self._grid_batch: pyglet.graphics.Batch = pyglet.graphics.Batch()
        self.setup_grid()

        # maps entity IDs to visual representations
        self._sprite_map: Dict[str, pyglet.sprite.Sprite] = {}
            
        # setting up the grid
        # self._grid_shader: ShaderProgram = self.gl_test_setup()
        # self._screen_attr_group: ScreenAttributeGroup = ScreenAttributeGroup(
        #     shader_program=self._grid_shader,
        #     screen_size=Vec2(x=self.width, y=self.height),
        #     grid_cell_size=self._grid_cell_size
        # )
        # self.gl_test(self._grid_shader)
        # self._grid_shader

    def load_visuals(self, entities: Dict[str,Entity]) -> None:
        """
        Loads the visual representations of entities into dict.
        """

        img: pyglet.resource.image
        sprite: pyglet.sprite.Sprite

        for thing in entities.keys():
            
            # load sprite from resources
            if entities[thing].sprite:
                img = pyglet.resource.image(entities[thing].sprite)
                img.anchor_x = img.width // 2
                img.anchor_y = img.height // 2
                sprite = pyglet.sprite.Sprite(
                    img=img,
                    x = self.height / 2,
                    y = self.width / 2,
                )
                sprite.scale = 0.01
                self._sprite_map[thing] = sprite

    def get_grid_coordinates(self, x: float, y: float) -> Tuple[int,int]:

        # 1 grid sqaure = 1 m^2
        # from meters -> pixels
        pixels_per_meter_x: int = self.width / self._grid_cell_size
        pixels_per_meter_y: int = self.height / self._grid_cell_size

        pixels_x: int = self._grid_origin[0] + int(pixels_per_meter_x * x)
        pixels_y: int = self._grid_origin[1] + int(pixels_per_meter_y * y)

        return pixels_x, pixels_y

    def run(self) -> None:
        pyglet.app.run()

    def schedule_loop(self, function, frequency: int = 20) -> None:
        pyglet.clock.schedule_interval(function, 1/frequency)

    def gl_test_setup(self) -> ShaderProgram:

        # a simple shader program
        vertex_shader: str = """#version 450 core
            layout (location = 0) in vec3 aPos;

            void main()
            {
                gl_Position = vec4(aPos.x, aPos.y, aPos.z, 1.0);
            }
        """
        fragment_shader: str = """#version 450 core
            out vec4 FragColor; // required for fragment shaders

            void main()
            {
                FragColor = vec4(1.0f, 0.5f, 0.2f, 1.0f);
            }
        """

        # grid
        grid_vertex_shader: str = """#version 450 core
            layout (location = 0) in vec3 aPos;

            uniform vec2 screenSize;
            uniform int tileSize;

            out vec3 pos;

            void main()
            {
                vec2 whatever;
                whatever = screenSize.xy / tileSize;

                gl_Position = vec4(aPos.x, aPos.y, aPos.z, 1.0);
                pos = aPos;
            }
        """
        grid_fragment_shader: str = """#version 450 core
            in vec3 pos;

            uniform vec2 screenSize;
            uniform int tileSize;

            out vec4 FragColor; // required for fragment shaders
            
            void main()
            {
                vec2 uv = pos.xy;
                
                vec2 tileCount = screenSize.xy / tileSize; 
                
                float edge = tileSize / 32.0;
                float face_tone = 0.9;
                float edge_tone = 0.5;
                // uv = sign(vec2(edge) - mod(uv, tileSize));
                FragColor = vec4(face_tone - sign(uv.x + uv.y + 2.0) * (face_tone - edge_tone));

                // FragColor = vec4(pos.x, pos.y, pos.z, 1.0);
            }
        """
        
        # a vec4 in opengl is (x,y,z,w) where w is perspective division (quaternions, baby!)

        # [PYGLET] pyglet requires that the shader be created before we can create vertices
        # if this were raw OpenGL, we would use glCreateShader()
        vert_shader: Shader = Shader(grid_vertex_shader, 'vertex')
        frag_shader: Shader = Shader(grid_fragment_shader, 'fragment')
        # [PYGLET] 'ShaderProgram's are collections of linked shaders
        #   analogous to glCreateProgram()
        test_program: ShaderProgram = ShaderProgram(vert_shader, frag_shader)

        return test_program

    def gl_test(self, shader_program: ShaderProgram = None):

        if not shader_program:
            # [PYGLET] we need the shader program first, before we can do anything else
            shader_program = self.gl_test_setup()

        # vertices_triangle: Tuple = (0.5, 0.5, 0.0,
        #                             0.5, -0.5, 0.0,
        #                             -0.5, -0.5, 0.0,
        #                             -0.5, 0.5, 0.0,
        #                             0.0, 0.5, 0.0)
        # vertices_rect: Tuple = (0.5, 0.5, 0.0,
        #                         0.5, -0.5, 0.0,
        #                         -0.5, -0.5, 0.0,
        #                         -0.5, 0.5, 0.0,)
        vertices_rect: Tuple = (1.0, 1.0, 0.0,
                                1.0, -1.0, 0.0,
                                -1.0, -1.0, 0.0,
                                -1.0, 1.0, 0.0,)

        # pre-req: generate vertex data (in normalized device coordinates [-1.0,1.0])
        #   VertexList has parameters created dynamically by loading the shaders into the ShaderProgram
        vertex_list: IndexedVertexList = shader_program.vertex_list_indexed(
            count=len(vertices_rect), 
            mode=pgl.GL_TRIANGLES,
            aPos=('fn', vertices_rect),
            indices=[0,1,3,1,2,3],
            batch=self._grid_batch,
            group=self._screen_attr_group
        )

        # the vertex buffer object (VBO) stores data in GPU memory
        # VBOs are abstracted away by pyglet, but otherwise we would bind + populate one here

        # element buffer objects (EBOs) store unique indices to draw to reduce 
        #   the overhead from redrawing common vertices

    def setup_grid(self):

        self._grid.clear()

        # pixel size
        x_step: int = self.width // self._grid_cell_size
        y_step: int = self.height // self._grid_cell_size

        print(f'(x_step,y_step) = ({x_step},{y_step})')

        # dumb and inefficient, but it only has to run periodically
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

    def move_sprite(self, id: str, x: int, y: int) -> None:
        
        try:
            self._sprite_map[id].x = x
            self._sprite_map[id].y = y
        except KeyError:
            print("fuck")

    def on_draw(self):
        
        self.clear()
        self._grid_batch.draw()
        
        for item in self._sprite_map.keys():
            self._sprite_map[item].draw()

    def on_resize(self, width, height) -> None:
        
        self._grid_batch = pyglet.graphics.Batch()
        self._grid.clear()
        self.setup_grid()
        
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