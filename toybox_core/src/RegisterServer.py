#!/usr/bin/env python3

from abc import ABC
from dataclasses import dataclass, field
import sys
from typing import Dict, List

import grpc
from google.protobuf.json_format import MessageToDict
import concurrent.futures as futures


# stupid hack because pip is the worst
sys.path.append('/home/dev/toybox')

import toybox_msgs.core.Register_pb2 as Register_pb2
import toybox_msgs.core.Register_pb2_grpc as Register_pb2_grpc

# from toybox_msgs.core.Metadata_pb2 import Metadata

class Message():
    """"
    wraps a protobuf class
    """
    pass


@dataclass
class Client():
    uuid: str
    addr: str
    port: str


class RegisterServicer(Register_pb2_grpc.RegisterServicer):

    def __init__(self, clients: Dict[str,Client]):
        self._clients = clients

    def RegisterClient(
        self, 
        request: Register_pb2.RegisterRequest, 
        context
    ) -> Register_pb2.RegisterResponse:

        client_id: str = request.client_id
        meta: Register_pb2.ClientMetadata = request.meta

        # we don't allow name collisions
        if self._clients.get(client_id) is not None:
            return Register_pb2.RegisterResponse(
                return_code=1,
                status=f"Client with ID {client_id} already registered.")

        self._clients[client_id] = Client(
            uuid=client_id, 
            addr=meta.addr,
            port=meta.port
        )
        return Register_pb2.ClientResponse(return_code=0)


class RegisterServer():
    
    def __init__(self, clients: Dict[str,Client] = {}) -> None:
        self._clients = clients
        self._servicer = RegisterServicer(clients=self._clients)
    
    def serve(self):
        
        self._server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        Register_pb2_grpc.add_RegisterServicer_to_server(
            self._servicer, 
            self._server
        )

        self._server.add_insecure_port('[::]:50051')
        
        self._server.start()

def main():

    pass
    # channel: grpc.insecure_channel = grpc.insecure_channel('localhost:50051')
    # stub: Client_pb2_grpc.ClientStub = Client_pb2_grpc.ClientStub(channel=channel)

    # client_req: Client_pb2.ClientRequest = Client_pb2.ClientRequest(
    #     client_id="butts",
    #     meta=Client_pb2.ClientMetadata(addr="butter", port="buttest")
    # )
    # conf: Client_pb2.ClientResponse = stub.RegisterClient(request=client_req)
    # print(conf)

if __name__ == "__main__":
    main()