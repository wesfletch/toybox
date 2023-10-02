#!/usr/bin/env python3

from abc import ABC
from dataclasses import dataclass, field
import sys
from typing import Dict, List, Tuple, Union

import grpc
import concurrent.futures as futures
import threading

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
    client_id: str
    addr: str
    rpc_port: int
    data_port: int

class RegisterServicer(Register_pb2_grpc.RegisterServicer):

    def __init__(self, clients: Dict[str,Client]):
        self._clients = clients

    def RegisterClient(
        self, 
        request: Register_pb2.RegisterRequest, 
        context: grpc.ServicerContext
    ) -> Register_pb2.RegisterResponse:

        # print(f'peer: {context.peer()}')

        client_id: str = request.client_id
        meta: Register_pb2.ClientMetadata = request.meta

        # we don't allow name collisions
        if self._clients.get(client_id) is not None:
            return Register_pb2.RegisterResponse(
                return_code=1,
                status=f"Client with ID <{client_id}> already registered.")

        self._clients[client_id] = Client(
            client_id=client_id, 
            addr=meta.addr,
            rpc_port=meta.port,
            data_port=meta.data_port if meta.data_port else -1
        )
        # print(self._clients)
        return Register_pb2.RegisterResponse(return_code=0)

    def DeRegisterClient(
        self, 
        request: Register_pb2.DeRegisterRequest, 
        context: grpc.ServicerContext,
    ) -> Register_pb2.RegisterResponse:

        client_id: str = request.client_id

        if self._clients.get(client_id) is None:
            return Register_pb2.RegisterResponse(
                return_code=1,
                status=f'No client with ID <{client_id}> registered.'
            )
        
        del self._clients[client_id]
        # print(self._clients)
        
        return Register_pb2.RegisterResponse(return_code=0)
    
    def GetClientInfo(
        self, 
        request: Register_pb2.Client_ID, 
        context: grpc.ServicerContext,
    ) -> Register_pb2.ClientResponse:

        client_id: str = request.client_id

        response: Register_pb2.ClientResponse = Register_pb2.ClientResponse()

        client: Union[Client,None] = self._clients.get(client_id, None)
        if client is None:
            response.return_code = 1
            response.status = f"No client found for client_id <{client_id}>"
            return response
        
        # build the response
        response_client = Register_pb2.ClientInfo()
        response_meta = Register_pb2.ClientMetadata()
        
        response_client.client_id = client.client_id
        response_meta.addr = client.addr
        response_meta.port = client.rpc_port
        response_meta.data_port = client.data_port

        response_client.meta.CopyFrom(response_meta)
        response.client.CopyFrom(response_client)

        response.return_code = 0

        return response

channel: grpc.insecure_channel = grpc.insecure_channel('localhost:50051')
register_stub: Register_pb2_grpc.RegisterStub = Register_pb2_grpc.RegisterStub(channel=channel)

class RegisterServer():
    
    def __init__(self, clients: Dict[str,Client] = {}) -> None:
        self._clients = clients
        self._servicer = RegisterServicer(clients=self._clients)
    
    def serve(self) -> None:
        
        self._server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        Register_pb2_grpc.add_RegisterServicer_to_server(
            self._servicer, 
            self._server
        )

        self._server.add_insecure_port('[::]:50051')
        
        self._server.start()
    
    def stop(self, grace: Union[float,None]) -> None: 
        
        stopping: threading.Event = self._server.stop(grace=grace)
        stopping.wait()


def register_client_rpc(
    name: str, 
    host: str,
    port: int,
    data_port: int = -1
) -> bool:
    
    # build our request
    client_req: Register_pb2.RegisterRequest = Register_pb2.RegisterRequest(
        client_id=name,
        meta=Register_pb2.ClientMetadata(addr=host, port=port, data_port=data_port)
    )
    result: Register_pb2.RegisterResponse = register_stub.RegisterClient(request=client_req)
    # print(result)
    return (result.return_code == 0)

def deregister_client_rpc(
    name: str,
) -> bool:
    
    # check if the server is still up
    try:
        grpc.channel_ready_future(channel=channel).result(timeout=0)
    except grpc.FutureTimeoutError:
        return True
    
    req: Register_pb2.DeRegisterRequest = Register_pb2.DeRegisterRequest(
        client_id=name
    )
    result: Register_pb2.RegisterResponse = register_stub.DeRegisterClient(request=req)
    # print(result)
    return (result.return_code == 0)

def get_client_info_rpc(
    client_name: str,
) -> Register_pb2.ClientInfo:
    
    client_req: Register_pb2.Client_ID = Register_pb2.Client_ID(
        client_id=client_name
    )
    result: Register_pb2.ClientResponse = register_stub.GetClientInfo(request=client_req)
    # print(result)

    return result.client


def main() -> None:

    # channel: grpc.insecure_channel = grpc.insecure_channel('localhost:50051')
    # stub: Client_pb2_grpc.ClientStub = Client_pb2_grpc.ClientStub(channel=channel)

    client_req: Register_pb2.RegisterRequest = Register_pb2.RegisterRequest(
        client_id="butts",
        meta=Register_pb2.ClientMetadata(addr="butter", port=27)
    )
    conf: Register_pb2.RegisterResponse = register_stub.RegisterClient(request=client_req)
    print(conf)

    client_id: Register_pb2.Client_ID = Register_pb2.Client_ID(
        client_id="butts"
    )
    conf_2: Register_pb2.ClientResponse = register_stub.GetClientInfo(request=client_id)
    print(conf_2)

if __name__ == "__main__":
    main()