#!/usr/bin/env python3

from toybox_sim.gui import SimWindow
from toybox_sim.simulation import Simulation

def main():
    
    sim: Simulation = Simulation(
        name="sim",
        window=SimWindow(),
        world="/home/wfletcher/toybox/toybox_sim/resources/base_config.json",)
    sim.run()

if __name__ == "__main__":
    main()
