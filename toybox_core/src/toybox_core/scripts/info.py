#!/usr/bin/env python3

import sys
from typing import List

from toybox_core.RegisterServer import Client, get_registered_clients_rpc


def list_clients() -> None:

    clients: List[Client] = get_registered_clients_rpc()
    for client in clients:
        print(str(client))

def main() -> None:

    assert len(sys.argv) >= 1, "Needs at least 1 argument"
    verb: str  = sys.argv[1]
    
    if verb == "clients":
        list_clients()
    else:
        print("What?")
        sys.exit(1)

if __name__ == "__main__":
    main()