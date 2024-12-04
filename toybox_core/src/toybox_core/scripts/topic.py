#!/usr/bin/env python3

import sys
from typing import List

from toybox_core.TopicServer import list_topics_rpc
from toybox_core.Topic import Topic

def list_topics() -> None:
    topics: List[Topic] = list_topics_rpc()
    if len(topics) == 0:
        print(f"No topics advertised.")
    for topic in topics:
        print(f"* {topic.name} : {topic.message_type}")

def main() -> None:

    verb: str = sys.argv[1]

    if verb == "list":
        list_topics()
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()