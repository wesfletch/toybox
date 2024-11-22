#!/usr/bin/env python3

from toybox_sim.gui import SimWindow
import toybox_sim.file_parse
from toybox_sim.world import World


def main():
    
    sim_window: SimWindow = SimWindow()

    worldy: World = toybox_sim.file_parse.parse_world_file(
        "~/toybox/toybox_sim/resources/base_config.json")
    worldy.window = sim_window

    worldy.run()


if __name__ == "__main__":
    main()
