from dataclasses import dataclass
from typing import List, Tuple

from math import pi as PI

class Polygon():
    """Simple polygon representation.
    """
    def __init__(self, points: List[Tuple[float, float]] = []):
        
        if not points:
            self._points: List[Tuple[float, float]] = []
        else:
            self._points = points

    @property
    def points(self) -> List[Tuple[float,float]]:
        return self._points

# 2D for now
@dataclass
class Position:
    """
    Position in 2-space.
    """
    x: float
    y: float

# 2D for now
@dataclass
class Orientation:
    """Orientation in 2D space.
    """
    theta: float # radians

# 2D for now
@dataclass
class Pose:
    position: Position
    orientation: Orientation

    def update(
        self,
        delta_p: Tuple[float,float,float]
    ) -> None:

        self.position.x = self.position.x + delta_p[0]
        self.position.y = self.position.y + delta_p[1]
        self.orientation.theta = (self.orientation.theta + delta_p[2]) % (2*PI)

class State:

    def __init__(self) -> None:
        pass 

