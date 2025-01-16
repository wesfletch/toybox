#!/usr/bin/env python3

import grpc

from toybox_msgs.core.Health_pb2 import (
    HealthCheckRequest, 
    HealthCheckResponse, 
    HealthState)
from toybox_msgs.core.Health_pb2_grpc import HealthServicer, HealthStub


class HealthRPCServicer(HealthServicer):

    def __init__(
        self,
    ) -> None:
        pass

    def Check(
        self, 
        request: HealthCheckRequest, 
        context: grpc.ServicerContext
    ) -> HealthCheckResponse:
        
        return HealthCheckResponse(
            health_state=HealthState.OK,
            status="OK")


def try_health_check_rpc(
    addr: str = "localhost", 
    port: int = 50051
) -> bool:
    
    channel: grpc.Channel = grpc.insecure_channel(f"{addr}:{port}")
    stub: HealthStub = HealthStub(channel=channel)

    try:
        response: HealthCheckResponse = stub.Check(HealthCheckRequest())
    except grpc.RpcError:
        return False
    
    if response.health_state != HealthState.OK:
        return False
    
    return True
