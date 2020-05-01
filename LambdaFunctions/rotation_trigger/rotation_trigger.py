#!/usr/bin/env python3

import boto3


def handler(event, context):
    arn = event['SecretArn']
    client = boto3.client("secretsmanager")
    print(f"Triggering rotation for secret '{arn}'")
    client.rotate_secret(SecretId=arn)
    print(f"Rotation for secret '{arn}' successfully triggered")
