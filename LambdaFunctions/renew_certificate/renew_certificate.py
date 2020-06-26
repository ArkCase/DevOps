#!/usr/bin/env python3

import os
import boto3
import botocore
import json


def handler(event, context):
    """Renew the given certificate.

    NB: This Lambda function is meant to be part of the `renew_certificates`
        state machine.

    Required environment variables:
      - CREATE_CERTIFICATE_LAMBDA_ARN: ARN of the `create_certificate` Lambda
        function

    The input `event` should look like this:

        {
            "S3Bucket": "XYZ",   # Bucket that contains the list of certificates to renew
            "S3Key": "XYZ",      # Key to the JSON file that contains the list of certificates to renew
            "Count": 17,         # Length of the above list
            "Index": 3,          # Index in the above list of the certificate to renew
            "IsFinished": false  # Whether all the certificates have been renewed or not
        }

    This Lambda function returns something like this:

        {
          "S3Bucket": "XYZ",  # Copy of the input
          "S3Key": "XYZ",     # Copy of the input
          "Count": 17,        # Copy of the input
          "Index": 17,        # Index of next certificate to renew
          "IsFinished": true  # Whether all the certificates have been renewed or not
        }
    """

    print(f"Received event: {event}")

    # Retrieve list of certificates to renew
    s3 = boto3.client("s3")
    response = s3.get_object(
        Bucket = event['S3Bucket'],
        Key=event['Key']
    )
    data = response['Body'].read().decode('utf8')
    cert_list = json.loads(data)

    # Build arguments to `create_certificate` Lambda function
    index = event['Index']
    certificate = cert_list[index]
    args = {
        'KeyType': certificate['KeyType'],
        'KeySize': certificate['KeySize'],
        'ValidityDays': certificate['ValidityDays']
    }

    add_arg_if_present(args, 'CountryName', event)
    add_arg_if_present(args, 'StateOrProvinceName', event)
    add_arg_if_present(args, 'LocalityName', event)
    add_arg_if_present(args, 'OrganizationName', event)
    add_arg_if_present(args, 'OrganizationalUnitName', event)
    add_arg_if_present(args, 'EmailAddress', event)
    add_arg_if_present(args, 'CommonName', event)
    add_arg_if_present(args, 'BasicConstraints', event)
    add_arg_if_present(args, 'KeyUsage', event)
    add_arg_if_present(args, 'SelfSigned', event)
    add_arg_if_present(args, 'CaKeyParameterName', event)
    add_arg_if_present(args, 'CaCertParameterName', event)

    args['KeyParameterName'] = event['KeyParameterName']
    args['CertParameterName'] = event['CertParameterName']

    add_arg_if_present(args, 'KeyTags', event)
    add_arg_if_present(args, 'CertTags', event)

    args['Cascade'] = False

    # Invoke the `create_certificate` Lambda function
    lambda_client = boto3.client("lambda")
    print(f"Invoking the `create_certificate` Lambda function")
    response = lambda_client.invoke(
        FunctionName=os.environ['CREATE_CERTIFICATE_LAMBDA_ARN'],
        LogType="Tail",
        Payload=json.dumps(args).encode('utf8')
    )
    print(f"`create_certificate` Lambda function returned: {response}")

    # Process the response
    body_json = response['Payload'].read().decode('utf8')
    print(f"`create_certificate` Lambda function response payload: {body_json}")
    if 'FunctionError' in response:
        err = response['FunctionError']
        raise ValueError(f"The `create_certificate` Lambda function failed: {err} - {body_json}")
    body = json.loads(body_json)
    if not body.get('Success', False):
        reason = "`create_certificate` Lambda function failed"
        if 'Reason' in body:
            reason += ": " + body['Reason']
        raise ValueError(reason)
    print(f"Successfully renewed certificate {cert_parameter_name}")

    output = event
    index += 1
    output['Index'] = index
    output['IsFinished'] = index >= output['Count']
    cert_parameter_name = certificate['CertParameterName']
    return output


def add_arg_if_present(args, name, event):
    if name in event:
        args[name] = event[name]
