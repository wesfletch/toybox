#!/usr/bin/env python3

import moderngl as mgl
import sdl2
import glcontext

ctx = mgl.create_context()

print(f"Default framebuffer is: {ctx.screen}")