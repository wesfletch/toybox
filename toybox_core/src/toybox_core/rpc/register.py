#!/usr/bin/env python3

from dataclasses import dataclass
from typing import Callable, Dict, List, Union

import grpc
import concurrent.futures as futures
import threading

from toybox_core.client import Client
from toybox_core.logging import LOG
from toybox_core.topic import Topic
import toybox_msgs.core.Register_pb2 as Register_pb2
import toybox_msgs.core.Register_pb2_grpc as Register_pb2_grpc
import toybox_msgs.core.Null_pb2 as Null_pb2


class RegisterServicer(Register_pb2_grpc.RegisterServicer):

    def __init__(
        self, 
        clients: Dict[str,Client],
        topics: Dict[str,Topic],
        deregister_callback: Callable[[str], bool] | None = None
    ) -> None:
        self._clients: Dict[str,Client] = clients
        self._topics: Dict[str,Topic] = topics

        self._deregister_callback: Callable[[str], bool] | None 
        self._deregister_callback = deregister_callback

    def RegisterClient(
        self, 
        request: Register_pb2.RegisterRequest, 
        context: grpc.ServicerContext
    ) -> Register_pb2.RegisterResponse:
        """
        RPC called by clients that wish to register with the TBX server.
        """

        client_id: str = request.client_id
        meta: Register_pb2.ClientMetadata = request.meta

        # We don't allow name collisions, client IDs MUST be unique
        if self._clients.get(client_id) is not None:
            LOG("WARN", f"Refused to register client with name <{client_id}>. Client with that ID already exists.")
            return Register_pb2.RegisterResponse(
                return_code=1,
                status=f"Client with ID <{client_id}> already registered.")

        new_client: Client = Client(
            client_id=client_id, 
            addr=meta.addr,
            rpc_port=meta.port,
            data_port=meta.data_port if meta.data_port else -1
        )
        LOG("WARN", f"START INITIALIZE {new_client.client_id}")
        new_client.initialize()
        LOG("WARN", f"FINISH INITIALIZE {new_client.client_id}")

        self._clients[client_id] = new_client
        
        LOG("INFO", f"Registered client <{client_id}> at <{meta.addr}>")
        
        return Register_pb2.RegisterResponse(return_code=0)

    def DeRegisterClient(
        self, 
        request: Register_pb2.DeRegisterRequest, 
        context: grpc.ServicerContext,
    ) -> Register_pb2.RegisterResponse:
        """
        RPC called by clients that wish to DE-register with the TBX server.
        """
        client_id: str = request.client_id

        if self._clients.get(client_id) is None:
            return Register_pb2.RegisterResponse(
                return_code=1,
                status=f'No client with ID <{client_id}> registered.')
        
        if self._deregister_callback is None:
            del self._clients[client_id]
            LOG("INFO", f"De-registered client <{client_id}>.")
            return Register_pb2.RegisterResponse(return_code=0)

        result: bool = self._deregister_callback(client_id)
        if not result:
            return Register_pb2.RegisterResponse(return_code=1, status="De-register callback failed.")

        LOG("INFO", f"De-registered client <{client_id}> with de-register callback.")
        return Register_pb2.RegisterResponse(return_code=0)
    
    def GetClientInfo(
        self, 
        request: Register_pb2.Client_ID, 
        context: grpc.ServicerContext,
    ) -> Register_pb2.ClientResponse:
        """
        RPC call for getting information about a specific TBX client.
        """

        client_id: str = request.client_id

        response: Register_pb2.ClientResponse = Register_pb2.ClientResponse()

        client: Client | None = self._clients.get(client_id, None)
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
    
    def GetRegisteredClients(
        self, 
        request: Null_pb2.Null, 
        context: grpc.ServicerContext
    ) -> Register_pb2.ClientList:
        """
        RPC call for getting a list of ALL registered TBX clients.
        """

        client_list: Register_pb2.ClientList = Register_pb2.ClientList()

        for _, client in self._clients.items():
            client_info: Register_pb2.ClientInfo = Register_pb2.ClientInfo()
            
            client_info.client_id = client.client_id
            client_meta: Register_pb2.ClientMetadata = Register_pb2.ClientMetadata(
                addr=client.addr,
                port=client.rpc_port,
                data_port=client.data_port)
            client_info.meta.CopyFrom(client_meta)
            
            client_list.clients.append(client_info)
        
        return client_list


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
    client_req: Register_pb2.RegisterRequest = Register_pb2.RegisterRequest()
    client_req.client_id = name
    client_req.meta.addr = host
    client_req.meta.port = port
    client_req.meta.data_port = data_port

    try:
        result: Register_pb2.RegisterResponse = register_stub.RegisterClient(request=client_req)
    except grpc.RpcError as e:
        LOG('ERR', f'Calling RegisterClient RPC failed: {e}')
        return False
    
    if result.return_code != 0:
        LOG("ERR", f"RPC failed: {result.status}")
    
    return (result.return_code == 0)

def deregister_client_rpc(
    name: str,
) -> bool:
    
    req: Register_pb2.DeRegisterRequest = Register_pb2.DeRegisterRequest(
        client_id=name
    )
    result: Register_pb2.RegisterResponse 
    try:
        result = register_stub.DeRegisterClient(request=req)
        LOG("DEBUG", f"De-registering client <{name}> returned <{result.return_code == 0}>.")
    except grpc.RpcError as e:
        LOG("ERR", f"Failed to de-register client {name}: {e}")
        return False
    
    return (result.return_code == 0)

def get_client_info_rpc(
    client_name: str,
) -> Register_pb2.ClientInfo:
    
    client_req: Register_pb2.Client_ID = Register_pb2.Client_ID(
        client_id=client_name
    )
    result: Register_pb2.ClientResponse = register_stub.GetClientInfo(request=client_req)

    return result.client

def get_registered_clients_rpc() -> Register_pb2.ClientList:

    request: Null_pb2.Null = Null_pb2.Null()
    result: Register_pb2.ClientList = register_stub.GetRegisteredClients(request=request)

    registered_clients: List[Client] = []
    for client_info in result.clients:
        client: Client = Client(
            client_id=client_info.client_id,
            addr=client_info.meta.addr,
            rpc_port=client_info.meta.port,
            data_port=client_info.meta.data_port
        )
        registered_clients.append(client)
    
    return registered_clients
