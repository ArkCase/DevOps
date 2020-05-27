#!/usr/bin/env python3

# This Lambda function assumes that the admin user (whose credentials are
# stored in the master secret) has been created by CloudFormation.

import boto3
import os
import json
import pymysql
import requests


def handler(event, context):
    """
    Handle an operation for a "MysqlDatabase" CloudFormation custom
    resource.

    The received event must have the following pattern:

        {
            "RequestType": "Create",
            "ResponseURL": "https://pre-signed-s3-url-for-response",
            "StackId": "arn:aws:cloudformation:us-west-1:123456789012:stack/stack-name/guid",
            "RequestId": "unique id for this request",
            "ResourceType": "Custom::MysqlDatabase",  # or whatever
            "LogicalResourceId": "MysqlDatabase",     # or whatever
            "ResourceProperties": {
                "SecretArn": "arn_to_master_secret",  # must be a JSON object formatted according to SecretsManager rotation requirements
                "DatabaseName": "some_db_name",
                "CharacterSet": "utf8",         # optional, defaults to "utf8"
                "Collation": "utf8_unicode_ci"  # optional, defaults to "utf8_unicode_ci"
            }
        }
    """
    try:
        handle_request(event)
    except Exception as e:
        print(f"ERROR: {str(e)}")
        send_response(event, False, str(e))
        return
    send_response(event, True, "Success")


def handle_request(event):
    # Parse the request
    request_type = event['RequestType']
    if request_type == "Delete":
        print(f"Request type is 'Delete'; not deleting the database here, the RDS instance will be destroyed anyway and we want it to produce a valid snapshot")
        return
    secret_arn = event['ResourceProperties']['SecretArn']
    database_name = event['ResourceProperties']['DatabaseName']
    character_set = event['ResourceProperties'].get('CharacterSet', "utf8")
    collation = event['ResourceProperties'].get('Collation', "utf8_unicode_ci")
    print(f"Request type     : {request_type}")
    print(f"Master secret ARN: {secret_arn}")
    print(f"Database name    : {database_name}")
    print(f"Character set    : {character_set}")
    print(f"Collation        : {collation}")

    # Build SQL statement
    if request_type == "Create":
        sql = f"CREATE DATABASE {database_name} CHARACTER SET '{character_set}' COLLATE '{collation}';"
        actioned = "created"
    elif request_type == "Update":
        sql = f"ALTER DATABASE {database_name} CHARACTER SET '{character_set}' COLLATE '{collation}';"
        actioned = "updated"
    else:
        raise ValueError(f"Unknow request type: '{request_type}'")

    # Get the master secret and connect to the RDS instance
    client = boto3.client("secretsmanager")
    value = client.get_secret_value(SecretId=secret_arn)
    master_secret = json.loads(value['SecretString'])
    host = master_secret['host']
    username = master_secret['username']
    password = master_secret['password']
    port = int(master_secret.get('port', 3306))
    print(f"Trying to connect to MySQL server: host={host}, user={username}, port={port}, db={database_name}")
    # NB: We want to connect using SSL. PyMySQL checks the `ssl` argument and
    #     enables SSL if it's not empty. PyMySQL docs says that the `ssl`
    #     argument should look like `mysql_ssl_set()`, but we don't need any of
    #     the items it sets. So I just used a random key, `enabled`, such that
    #     the `ssl` argument is a non-empty dictionary to fool PyMySQL. It
    #     looks like it's working fine.
    cnx = pymysql.connect(
            host=host,
            user=username,
            passwd=password,
            port=port,
            connect_timeout=5,
            ssl={'enabled': True})
    print(f"Successfully connected to MySQL server")

    # Run SQL statement
    print(f"Executing SQL: {sql}")
    cnx.cursor().execute(sql)
    print(f"Successfully {actioned} database '{database_name}'")
    cnx.close()


def send_response(event, success: bool, msg="", data={}):
    response = {
        'Status': "SUCCESS" if success else "FAILED",
        'Reason': msg,
        'PhysicalResourceId': event['ResourceProperties'].get('DatabaseName', "nothing"),
        'StackId': event['StackId'],
        'RequestId': event['RequestId'],
        'LogicalResourceId': event['LogicalResourceId'],
        'Data': data
    }
    headers = {
        'Content-Type': ""
    }
    body = json.dumps(response)
    print(f"Sending response back to CloudFormation: {response['Status']}")
    requests.put(event['ResponseURL'], headers=headers, data=body)
    print(f"Response successfully sent to CloudFormation")
