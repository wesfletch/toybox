#!/usr/bin/env python3

from toybox_sim.gui import SimWindow
from toybox_sim.simulation import Simulation
from toybox_sim.file_parse import parse_world_file


def main():
    
    sim: Simulation = Simulation(
        name="sim",
        window=SimWindow(),
        world=parse_world_file(
            "/home/wfletcher/toybox/toybox_sim/resources/base_config.json"),
    )
    sim.run()

if __name__ == "__main__":
    main()
