#!/usr/bin/env python3

import traceback
import boto3
import botocore
import json
import requests


def handler(event, context):
    """
    Create a certificate that is either self-signed ro signed by a CA.

    The event received has the following pattern (the fields are mandatory
    unless marked as "optional"):

        {
          "RequestType": "Create",
          "ResponseURL": "https://pre-signed-s3-url-for-response",
          "StackId": "arn:aws:cloudformation:us-west-2:123456789012:stack/stack-name/guid",
          "RequestId": "unique id for this request",
          "ResourceType": "Custom::Certificate",   # or whatever
          "LogicalResourceId": "Certificate",      # or whatever
          "ResourceProperties": {
            "CertificateLambdaArn": "arn:...",   # Name of the `certificate` Lambda function
            "KeyType": "RSA",                    # Or "DSA"; optional, defaults to "RSA"
            "KeySize": 2048,                     # Key size
            "ValidityDays": 100,                 # For how many days the certificate should be valid

            "CountryName": "US",                 # Optional
            "StateOrProvinceName": "VA",         # Optional
            "LocalityName": "Vienna",            # Optional
            "OrganizationName": "Armedia, LLC",  # Optional
            "OrganizationalUnitName": "SecOps",  # Optional
            "EmailAddress": "bob@builder.com",   # Optional
            "CommonName": "arkcase.internal",    # Optional in theory, required in practice

            "BasicConstraints": {     # Basic constraints extension, optional
              "Critical": true,       # Whether these basic constraints are critical; optional, default to `false`
              "CA": true,             # Whether this certificate can sign certificates; optional, default to `false`
              "PathLength": 3         # Max length of the chain; optional, default to `null` (which means "no limit")
            },

            "KeyUsage": {             # Key usage extension, optional
              "Critical": true,       # Whether these key usages are critical; optional, default to `false`
              "Usages": [             # List of usages; absent means "no"
                "DigitalSignature",   # Can verify digital signature
                "ContentCommitment",  # Non-repudiation
                "KeyEncipherment",    # Can encrypt keys
                "DataEncipherment",   # Can encrypt data
                "KeyAgreement",       # Key agreement (eg: DH)
                "KeyCertSign",        # Can sign certificates; if set, `BasicConstraints.CA` must be set to `true`
                "CrlSign",            # Can sign CRLs
                "EncipherOnly",       # Can encrypt following a key agreement
                "DecipherOnly"        # Can decrypt following a key agreement
              ]
            },

            # Name of the parameters storing the private key and certificate of
            # the CA that will be used to sign this new certificate. If either
            # is missing, a self-signed certificate will be issued.
            "CaKeyParameterName": "XYZ",
            "CaCertParameterName": "XYZ",

            # Name of the SSM parameter where to save the private key
            "KeyParameterName": "/arkcase/pki/private/my-key",
            "CertParameterName": "/arkcase/pki/certs/my-cert",

            "KeyTags": [  # Tags for the private key parameter, optional
              {
                "Key": "Name",
                "Value": "my private key"
              },
              {
                "Key": "ABC",
                "Value": "XYZ"
              }
            ],

            "CertTags": [  # Tags for the certificate parameter, optional
              {
                "Key": "Name",
                "Value": "my certificate"
              },
              {
                "Key": "ABC",
                "Value": "XYZ"
              }
            ]
          }
        }

    The ARNs of the private key and certificate parameters will be returned and
    made available through `Fn::GetAtt`:

        !GetAtt Certificate.KeyParameterArn
        !GetAtt Certificate.CertParameterArn

    """
    try:
        reason, key_param_arn, cert_param_arn = handle_request(event)
        print(f"Success")
        send_response(event, True, reason, key_param_arn, cert_param_arn)
    except Exception as e:
        traceback.print_exc()
        send_response(event, False, str(e))


def handle_request(event):
    request_type = event['RequestType']
    print(f"Received request type: {request_type}")
    if request_type == "Create" or request_type == "Update":
        ret = upsert_certificate(event)
    elif request_type == "Delete":
        ret = delete_certificate(event)
    else:
        raise ValueError(f"Invalid request type: {request_type}")
    return ret


def upsert_certificate(event):
    print(f"Creating/renewing certificate")

    # Check the key and certificate parameter names do not have commas
    args = event['ResourceProperties']
    if "," in args['KeyParameterName'] or "," in args['CertParameterName']:
        raise ValueError(f"Commas not allowed in key or certificate parameter name")

    # Build payload to `certificate` Lambda function
    # NB: CloudFormation changes all types to "string", so we have to cast all
    #     fields that are not strings.
    payload = args
    payload['KeySize'] = int(payload['KeySize'])
    payload['ValidityDays'] = int(payload['ValidityDays'])
    if 'BasicConstraints' in payload:
        bc = payload['BasicConstraints']
        if 'Critical' in bc:
            bc['Critical'] = bc['Critical'] == "true"
        if 'CA' in bc:
            bc['CA'] = bc['CA'] == "true"
        if 'PathLength' in bc:
            if bc['PathLength'] == "null":
                bc['PathLength'] = None
            else:
                bc['PathLength'] = int(bc['PathLength'])
    if 'KeyUsage' in payload:
        ku = payload['KeyUsage']
        if 'Critical' in ku:
            ku['Critical'] = ku['Critical'] == "true"


    # Call the `certificate` Lambda function
    lambda_arn = args['CertificateLambdaArn']
    lambda_client = boto3.client("lambda")
    print(f"Invoking `certificate` Lambda function")
    response = lambda_client.invoke(
        FunctionName=lambda_arn,
        LogType="Tail",
        Payload=json.dumps(args).encode('utf8')
    )
    print(f"`certificate` Lambda function returned: {response}")

    # Process the response
    body_json = response['Payload'].read().decode('utf8')
    print(f"`certificate` Lambda function response payload: {body_json}")
    if 'FunctionError' in response:
        err = response['FunctionError']
        raise ValueError(f"The `certificate` Lambda function failed: {err} - {body_json}")
    body = json.loads(body_json)
    if body.get('Success', False):
        reason = body['Reason']
        key_param_arn = body['KeyParameterArn']
        cert_param_arn = body['CertParameterArn']
        print(f"Successfully created/renewed certificate: reason: {reason}, key_param_arn: {key_param_arn}, cert_param_arn: {cert_param_arn}")
        return reason, key_param_arn, cert_param_arn
    else:
        reason = "`certificate` Lambda function failed"
        if 'Reason' in body:
            reason += ": " + body['Reason']
        raise ValueError(reason)


def delete_certificate(event):
    physical_id = event['PhysicalResourceId']
    print(f"Deleting certificate; physical_id: {physical_id}")
    # Parse the physical id to get the key and certificate parameter names
    key_param_name, cert_param_name = physical_id.split(",")
    ssm = boto3.client("ssm")
    if key_param_name:
        ssm.delete_parameter(Name=key_param_name)
    if cert_param_name:
        ssm.delete_parameter(Name=cert_param_name)
    return "Success", "", ""


def send_response(event, success: bool, reason, key_param_arn="", cert_param_arn=""):
    if not 'KeyParameterName' in event or not 'CertParameterName' in event:
        print(f"WARNING: Either KeyParameterName, CertParameterName, or both are absent from the arguments")
        physial_id = ","
    else:
        physial_id = event['KeyParameterName'] + "," + event['CertParameterName']
    response = {
        'Status': "SUCCESS" if success else "FAILED",
        'Reason': reason,
        'PhysicalResourceId': physial_id,
        'StackId': event['StackId'],
        'RequestId': event['RequestId'],
        'LogicalResourceId': event['LogicalResourceId'],
        'Data': {
            'KeyParameterArn': key_param_arn,
            'CertParameterArn': cert_param_arn
        }
    }
    headers = {
        'Content-Type': ""
    }
    body = json.dumps(response)
    requests.put(event['ResponseURL'], headers=headers, data=body)
