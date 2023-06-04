#!/usr/bin/env python3

import sys
import signal
import random
from typing import Tuple
import time

import pygame
from pygame.locals import KEYDOWN, K_q

# CONSTANTS
SCREENSIZE = WIDTH, HEIGHT = 600,400

BLACK: pygame.Color = pygame.Color(0,0,0,255)
GREY: pygame.Color = pygame.Color(160,160,160,255)
WHITE: pygame.color = pygame.Color(255,255,255,255)
RED: pygame.Color = pygame.Color(255,0,0,255)
EMPTY: pygame.Color = pygame.Color(0,0,0,0)

_CONTROL = {'display_mode': None}

def ctrl_c_handler(signum, frame):
    # print('CTRL-C. Exiting.')    
    sys.exit(1) 

def check_events():

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            sys.exit()
        elif event.type == KEYDOWN and event.key == K_q:
            pygame.quit()
            sys.exit()

def draw_rect(
    surface: pygame.Surface, 
    size_x: int, 
    size_y: int, 
    origin: Tuple[int, int] = (0,0), 
    color: pygame.Color = BLACK
) -> None:
    """Draw a rectangle on a given pygame.Surface

    Args:
        surface (pygame.Surface): Surface to draw rectangle
        size_x (int): size of rectangle in x dimension
        size_y (int): size of rectangle in y dimension
        origin (Tuple[int, int]): origin of rectangle relative to surface
        color (pygame.Color, optional): color of rectangle. Defaults to BLACK.
    """
    # top-left point
    x_0 = origin[0]
    y_0 = origin[1]
    
    rect: pygame.Rect = pygame.Rect(x_0, y_0, size_x, size_y)
    pygame.draw.rect(surface, color, rect)

def get_grid_square(
    square_size: int,
    border_width: int = 1,
    square_color: pygame.Color = WHITE,
    border_color: pygame.Color = GREY 
) -> pygame.Surface:
    """Create a pygame.Surface containing a grid square with border 

    Args:
        square_size (int): total size of the grid square
        border_width (int, optional): width of border in pixels. Defaults to 1.
        square_color (pygame.Color, optional): interior color of grid square. Defaults to GREY.
        border_color (pygame.Color, optional): border color of grid square. Defaults to BLACK.

    Returns:
        pygame.Surface: A Surface containing a single grid square.
    """

    surf: pygame.Surface = pygame.Surface((square_size, square_size), pygame.SRCALPHA)
    
    # draw the "border"
    draw_rect(surf, square_size, square_size, (0,0), border_color)

    # draw the interior square on top of border
    interior_size: int = square_size - (2 * border_width)
    draw_rect(surf, interior_size, interior_size, (border_width, border_width), square_color)

    return surf

def draw_grid(
    surface: pygame.Surface,
    square_size: int
) -> None:
    """Draw grid on provided pygame.Surface

    Args:
        surface (pygame.Surface): Surface to draw the grid on
        square_size (int): _description_
    """
    surface_height: int = surface.get_height()
    surface_width: int = surface.get_width()

    idx: int = 0
    idy: int = 0
    while idx <= surface_width:
        while idy <= surface_height:
            grid_square: pygame.Surface = get_grid_square(square_size)
            surface.blit(grid_square, (idx,idy))
            idy += square_size
        idx += square_size 
        idy = 0

def main():

    pygame.init()
    _CONTROL['display_mode'] = pygame.display.set_mode(SCREENSIZE)

    # signal handling
    signal.signal(signal.SIGINT, ctrl_c_handler)

    while True:
        check_events()
        _CONTROL['display_mode'].fill(EMPTY)
        
        draw_grid(_CONTROL['display_mode'], 10)
        
        pygame.display.flip()

if __name__=='__main__':
    main()
