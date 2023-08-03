
from toybox_core.src.TopicServer import TopicServer
from toybox_core.src.RegisterServer import ClientServer

def main():

    server: TopicServer = TopicServer()
    # server.serve()

    client_server: ClientServer = ClientServer()
    client_server.serve()

if __name__ == "__main__":
    main()