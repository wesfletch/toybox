#!/usr/bin/env python3

import os
import sys

from toybox_core.client import Client
from toybox_core.rpc.register import get_registered_clients_rpc
from toybox_core.metadata import find_tbx_packages, ToyboxMetadata


def list_clients() -> None:

    clients: list[Client] = get_registered_clients_rpc()
    for client in clients:
        print(str(client))

def list_packages() -> None:

    all_pkgs: dict[str,ToyboxMetadata] = find_tbx_packages()
    for package in all_pkgs.values():
        print(f"{package.package_name}: {package.package_root}")


def info_about_package(package_name: str) -> None:

    all_pkgs: dict[str,ToyboxMetadata] = find_tbx_packages()
    meta: ToyboxMetadata | None = all_pkgs.get(package_name, None)

    if meta is None:
        print(f"Couldn't find info about package <{package_name}>")
        return

    print(meta.human_readable())


def main() -> None:

    assert len(sys.argv) >= 1, "Needs at least 1 argument"
    verb: str  = sys.argv[1]
    
    if verb == "clients":
        list_clients()
    elif verb == "package":
        package_name: str | None = None
        try:
            package_name = sys.argv[2]
            info_about_package(package_name=package_name)
        except IndexError:
            list_packages()
    else:
        print("What?")
        sys.exit(1)
    
    sys.exit(0)

if __name__ == "__main__":
    main()