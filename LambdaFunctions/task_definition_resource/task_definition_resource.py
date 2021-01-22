#!/usr/bin/env python3
#
# Copyright (c)  2020  Fabrice Triboix

import traceback
import boto3
import json
import requests


def handler(event, context):
    """
    Lambda backend for a task definition custom resource for CloudFormation.
    This custom resource supports all the current parameters for a task
    definition, including EFS volumes which are not supported by CloudFormation
    yet as of 20200729.

    The received event has the following pattern:

        {
            "RequestType": "Create",  # Or "Update" or "Delete"
            "ResponseURL": "https://pre-signed-S3-url",
            "StackId": "arn:...",
            "RequestId": "unique id for this request",
            "ResourceType": "Custom::TaskDefinition",
            "LogicalResourceId": "MyTaskDef",
            "ResourceProperties": {
                # Exactly the same as required for the
                # `register_task_definition` API call, more details
                # [here](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ecs.html#ECS.Client.register_task_definition).
            }
        }
    """
    try:
        physical_id = handle_request(event)
        send_response(
                event,
                True,
                "Successfully registered task definition",
                physical_id
        )
    except Exception as e:
        traceback.print_exc()
        send_response(event, False, str(e), "none")


def handle_request(event):
    ecs_client = boto3.client('ecs')
    request_type = event['RequestType']
    if request_type == "Create" or request_type == "Update":
        return register_taskdef(ecs_client, event)
    elif request_type == "Delete":
        return deregister_taskdef(ecs_client, event)
    else:
        raise ValueError(f"Unknown request type: {request_type}")


def register_taskdef(ecs_client, event):
    kwargs = event['ResourceProperties']
    if 'ServiceToken' in kwargs:
        del kwargs['ServiceToken']

    # CloudFormation transforms all values into string, so we need to change
    # back to the correct types.
    if 'containerDefinitions' in kwargs:
        for i in kwargs['containerDefinitions']:
            if 'cpu' in i:
                i['cpu'] = int(i['cpu'])
            if 'disableNetworking' in i:
                i['disableNetworking'] = i['disableNetworking'].lower() == "true"
            if 'essential' in i:
                i['essential'] = i['essential'].lower() == "true"
            if 'healthCheck' in i:
                health_check = i['healthCheck']
                if 'interval' in health_check:
                    health_check['interval'] = int(health_check['interval'])
                if 'retries' in health_check:
                    health_check['retries'] = int(health_check['retries'])
                if 'startPeriod' in health_check:
                    health_check['startPeriod'] = int(health_check['startPeriod'])
                if 'timeout' in health_check:
                    health_check['timeout'] = int(health_check['timeout'])
            if 'interactive' in i:
                i['interactive'] = i['interactive'].lower() == "true"
            if 'linuxParameters' in i:
                p = i['linuxParameters']
                if 'initProcessEnabled' in p:
                    p['initProcessEnabled'] = p['initProcessEnabled'].lower() == "true"
                if 'maxSwap' in p:
                    p['maxSwap'] = int(p['maxSwap'])
                if 'sharedMemorySize' in p:
                    p['sharedMemorySize'] = int(p['sharedMemorySize'])
                if 'swappiness' in p:
                    p['swappiness'] = int(p['swappiness'])
                if 'tmpfs' in p:
                    for j in p['tmpfs']:
                        if 'size' in j:
                            j['size'] = int(j['size'])
            if 'memory' in i:
                i['memory'] = int(i['memory'])
            if 'memoryReservation' in i:
                i ['memoryReservation'] = int(i['memoryReservation'])
            if 'mountPoints' in i:
                for j in i['mountPoints']:
                    if 'readOnly' in j:
                        j['readOnly'] = j['readOnly'].lower() == "true"
            if 'portMappings' in i:
                for j in i['portMappings']:
                    if 'containerPort' in j:
                        j['containerPort'] = int(j['containerPort'])
                    if 'hostPort' in j:
                        j['hostPort'] = int(j['hostPort'])
            if 'privileged' in i:
                i['privileged'] = i['privileged'].lower() == "true"
            if 'pseudoTerminal' in i:
                i['pseudoTerminal'] = i['pseudoTerminal'].lower() == "true"
            if 'readonlyRootFilesystem' in i:
                i['readonlyRootFilesystem'] = i['readonlyRootFilesystem'].lower() == "true"
            if 'startTimeout' in i:
                i['startTimeout'] = i['startTimeout'].lower() == "true"
            if 'stopTimeout' in i:
                i['stopTimeout'] = i['stopTimeout'].lower() == "true"
            if 'ulimits' in i:
                for j in i['ulimits']:
                    if 'hardLimit' in j:
                        j['hardLimit'] = int(j['hardLimit'])
                    if 'softLimit' in j:
                        j['softLimit'] = int(j['softLimit'])
            if 'volumesFrom' in i:
                for j in i['volumesFrom']:
                    if 'readOnly' in j:
                        j['readOnly'] = j['readOnly'].lower() == "true"

    if 'volumes' in kwargs:
        for i in kwargs['volumes']:
            if 'dockerVolumeConfiguration' in i:
                j = i['dockerVolumeConfiguration']
                if 'autoprovision' in j:
                    j['autoprovision'] = j['autoprovision'].lower() == "true"
            if 'efsVolumeConfiguration' in i:
                j = i['efsVolumeConfiguration']
                if 'transitEncryptionPort' in j:
                    j['transitEncryptionPort'] = int(j['transitEncryptionPort'])

    print(f"Calling register_task_definition; kwargs={kwargs}")
    response = ecs_client.register_task_definition(**kwargs)
    return response['taskDefinition']['taskDefinitionArn']


def deregister_taskdef(ecs_client, event):
    taskdef_arn = event['PhysicalResourceId']
    if taskdef_arn != "none":
        ecs_client.deregister_task_definition(taskDefinition=taskdef_arn)
    return taskdef_arn


def send_response(event: dict, success: bool, msg: str, physical_id: str):
    response = {
        'Status': "SUCCESS" if success else "FAILED",
        'PhysicalResourceId': physical_id,
        'StackId': event['StackId'],
        'RequestId': event['RequestId'],
        'LogicalResourceId': event['LogicalResourceId']
    }
    if msg:
        response['Reason'] = msg
    elif not success:
        response['Reason'] = "No reason provided"
    headers = {
        'Content-Type': ""
    }
    body = json.dumps(response)
    print(f"Sending response {body}")
    url = event['ResponseURL']
    requests.put(url, headers=headers, data=body)
