import os
import traceback
import boto3
import botocore
import json
import requests
from libarkcert import create_or_renew_cert


def handler(event, context):
    """
    Create a certificate that is either self-signed or signed by a CA.

    The following environment variables must be set:
      - RENEW_CERTIFICATES_STATE_MACHINE_ARN: ARN of the `renew_certificate`
        AWS Step Functions state machine

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

            # Whether this certificate should be self-signed or signed by a CA.
            # If set to `false`, you must also set the `CaKeyParameterName` and
            # `CaCertParameterName` to valid values.
            #
            # Optional; default to `false`
            "SelfSigned": false,

            # Name of the parameters storing the private key and certificate of
            # the CA that will be used to sign this new certificate. If
            # `SelfSigned` is set to `false`, those fields are mandatory.
            "CaKeyParameterName": "XYZ",
            "CaCertParameterName": "XYZ",

            # Name of the SSM parameter where to save the private key
            "KeyParameterName": "/arkcase/pki/private/my-key",
            # Name of the SSM parameter where to save the certificate
            "CertParameterName": "/arkcase/pki/certs/my-cert",

            "KeyTags": [  # Tags for the private key parameter, optional
              {
                "Key": "tag key 1",
                "Value": "tag value 1"
              },
              {
                "Key": "tag key 2",
                "Value": "tag value 2"
              }
            ],

            "CertTags": [  # Tags for the certificate parameter, optional
              {
                "Key": "tag key 1",
                "Value": "tag value 1"
              },
              {
                "Key": "tag key 2",
                "Value": "tag value 2"
              }
            ]
          }
        }

    The ARNs of the private key and certificate parameters will be returned and
    made available through `Fn::GetAtt`:

        !GetAtt Certificate.KeyParameterArn
        !GetAtt Certificate.CertParameterArn

    """
    print(f"Received event: {event}")
    try:
        reason, key_parameter_arn, cert_parameter_arn = handle_request(event)
        print(f"Success")
        send_response(event, True, reason, key_parameter_arn, cert_parameter_arn)
    except Exception as e:
        traceback.print_exc()
        send_response(event, False, str(e))


def handle_request(event):
    request_type = event['RequestType']
    print(f"Received request type: {request_type}")
    if request_type == "Create" or request_type == "Update":
        ret = upsert_certificate(event, request_type)
    elif request_type == "Delete":
        ret = delete_certificate(event)
    else:
        raise ValueError(f"Invalid request type: {request_type}")
    return ret


def upsert_certificate(event, request_type):
    args = event['ResourceProperties']
    cert_parameter_name = args['CertParameterName']
    print(f"Creating/renewing certificate {cert_parameter_name}")

    # NB: CloudFormation changes all types to "string", so we have to cast all
    #     non-string fields back to their original types.
    args['KeySize'] = int(args['KeySize'])
    args['ValidityDays'] = int(args['ValidityDays'])
    if 'BasicConstraints' in args:
        bc = args['BasicConstraints']
        if 'Critical' in bc:
            bc['Critical'] = bc['Critical'].lower() == "true"
        if 'CA' in bc:
            bc['CA'] = bc['CA'].lower() == "true"
        if 'PathLength' in bc:
            if bc['PathLength'].lower() == "null":
                bc['PathLength'] = None
            else:
                bc['PathLength'] = int(bc['PathLength'])
    if 'KeyUsage' in args:
        ku = args['KeyUsage']
        if 'Critical' in ku:
            ku['Critical'] = ku['Critical'].lower() == "true"
    if 'SelfSigned' in args:
        args['SelfSigned'] = args['SelfSigned'].lower() == "true"

    # Create/renew the certificate
    key_parameter_arn, cert_parameter_arn = create_or_renew_cert(args)

    # Check if the key and/or certificate parameter name(s) have changed. If
    # yes, delete the old parameters.
    if 'OldResourceProperties' in event:
        ssm = boto3.client("ssm")
        old_args = event['OldResourceProperties']
        old_key_parameter_name = old_args['KeyParameterName']
        if args['KeyParameterName'] != old_key_parameter_name:
            print(f"Key parameter name has changed; deleting old key parameter {old_key_parameter_name}")
            ssm.delete_parameter(Name=old_key_parameter_name)
        old_cert_parameter_name = old_args['CertParameterName']
        if args['CertParameterName'] != old_cert_parameter_name:
            print(f"Certificate parameter name has changed; deleting old certificate parameter {old_cert_parameter_name}")
            ssm.delete_parameter(Name=old_cert_parameter_name)

    if request_type == "Update":
        # NB: When a certificate is renewed through the CloudFormation template
        #     (eg: a parameter changes, such as `OrganizationalUnitName`) and
        #     it is a CA, we need to renew certificates that depend on it as
        #     well.
        is_ca = args.get('BasicConstraints', {}).get('CA', False)
        if is_ca:
            print(f"This certificate is a CA, requesting renewals for dependent certificates")
            sfn = boto3.client("stepfunctions")
            data = {
                'ParentCertParameterArn': cert_parameter_arn
            }
            sfn.start_execution(
                stateMachineArn=os.environ['RENEW_CERTIFICATES_STATE_MACHINE_ARN'],
                input=json.dumps(data)
            )

    # Done
    print(f"Successfully created/renewed certificate: key_parameter_arn: {key_parameter_arn}, cert_parameter_arn: {cert_parameter_arn}")
    return "Success", key_parameter_arn, cert_parameter_arn


def delete_certificate(event):
    physical_id = event['PhysicalResourceId']
    print(f"Deleting certificate; physical_id: {physical_id}")
    # Parse the physical id to get the key and certificate parameter names
    key_parameter_name, cert_parameter_name = physical_id.split(",")
    ssm = boto3.client("ssm")
    if key_parameter_name:
        try:
            ssm.delete_parameter(Name=key_parameter_name)
        except ssm.exceptions.ParameterNotFound as e:
            # Already deleted by the previous update
            pass
    if cert_parameter_name:
        try:
            ssm.delete_parameter(Name=cert_parameter_name)
        except ssm.exceptions.ParameterNotFound as e:
            # Already deleted by the previous update
            pass
    return "Success", "", ""


def send_response(event, success: bool, reason, key_parameter_arn="", cert_parameter_arn=""):
    args = event['ResourceProperties']
    if not 'KeyParameterName' in args or not 'CertParameterName' in args:
        print(f"WARNING: Either KeyParameterName, CertParameterName, or both are absent from the arguments")
        physical_id = ","
    else:
        physical_id = args['KeyParameterName'] + "," + args['CertParameterName']
    response = {
        'Status': "SUCCESS" if success else "FAILED",
        'Reason': reason,
        'PhysicalResourceId': physical_id,
        'StackId': event['StackId'],
        'RequestId': event['RequestId'],
        'LogicalResourceId': event['LogicalResourceId'],
        'Data': {
            'KeyParameterArn': key_parameter_arn,
            'CertParameterArn': cert_parameter_arn
        }
    }
    headers = {
        'Content-Type': ""
    }
    body = json.dumps(response)
    requests.put(event['ResponseURL'], headers=headers, data=body)
