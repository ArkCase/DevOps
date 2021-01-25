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

            "SubjectAlternativeName": {  # Subject alternative name extension, optional
              "Critical": true,          # Whether this SAN is critical; optional, default to `false`
              "DNS": [                   # Name type; currently, the only valid value is "DNS"
                "name1.example.com",     # Alternative name
                "name2.example.com"      # Alternative name
              ]
            },

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

            # Name of the SSM parameters storing the private key and
            # certificate of the CA that will be used to sign this new
            # certificate. If `SelfSigned` is set to `false`, those fields are
            # mandatory.
            "CaKeyParameterName": "XYZ",
            "CaCertParameterName": "XYZ",

            # Name of the SSM parameter where to save the private key
            "KeyParameterName": "/arkcase/pki/private/my-key",
            # Name of the SSM parameter where to save the certificate
            "CertParameterName": "/arkcase/pki/certs/my-cert",

            "KeyTags": [  # Tags for the private key SSM parameter, optional
              {
                "Key": "tag key 1",
                "Value": "tag value 1"
              },
              {
                "Key": "tag key 2",
                "Value": "tag value 2"
              }
            ],

            "CertTags": [  # Tags for the certificate SSM parameter, optional
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

    The ARNs and names of the private key and certificate SSM parameters will
    be returned and made available through `Fn::GetAtt`, along with the IAM
    server certificate name:

        !GetAtt Certificate.KeyParameterArn
        !GetAtt Certificate.CertParameterArn
        !GetAtt Certificate.KeyParameterName
        !GetAtt Certificate.CertParameterName
        !GetAtt Certificate.IamCertName

    """
    print(f"Received event: {event}")
    try:
        handle_request(event)
    except Exception as e:
        traceback.print_exc()
        send_response(event, False, str(e))


def handle_request(event):
    request_type = event['RequestType']
    print(f"Received request type: {request_type}")
    if request_type == "Create" or request_type == "Update":
        upsert_certificate(event, request_type)
    elif request_type == "Delete":
        delete_certificate(event)
    else:
        raise ValueError(f"Invalid request type: {request_type}")


def upsert_certificate(event, request_type):
    args = event['ResourceProperties']
    key_parameter_name = args['KeyParameterName']
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
    if 'SubjectAlternativeName' in args:
        san = args['SubjectAlternativeName']
        if 'Critical' in san:
            san['Critical'] = san['Critical'].lower() == "true"
    if 'SelfSigned' in args:
        args['SelfSigned'] = args['SelfSigned'].lower() == "true"

    # Create/renew the certificate
    # NB: This will also save it in SSM and IAM
    key_parameter_arn, cert_parameter_arn, iam_cert_name, iam_cert_arn = create_or_renew_cert(args)
    print(f"Successfully created/renewed certificate: key_parameter_arn: {key_parameter_arn}, cert_parameter_arn: {cert_parameter_arn}, iam_cert_arn: {iam_cert_arn}")

    # Check if the key and/or certificate parameter name(s) have changed. If
    # yes, delete the old parameters.
    #
    # NB: For an `Update` operation only, CloudFormation sets the
    #     `OldResourceProperties` to the parameters of the resource as they
    #     were before the `Update` request.
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

            path_items = cert_parameter_name.split("/")
            old_cert_name = path_items.pop()
            iam = boto3.client("iam")
            iam.delete_server_certificate(ServerCertificateName=old_cert_name)

    # When a certificate is renewed through the CloudFormation template (eg: a
    # parameter changes, such as `OrganizationalUnitName`) and it is a CA, we
    # need to renew certificates that depend on it as well.
    is_ca = args.get('BasicConstraints', {}).get('CA', False)
    if request_type == "Update" and is_ca:
        print(f"This certificate {cert_parameter_name} is a CA, requesting renewals for dependent certificates")
        sfn = boto3.client("stepfunctions")
        data = {
            'Input': {
                'ParentCertParameterArn': cert_parameter_arn,
            },
            'CloudFormationData': {
              'ResponseURL': event['ResponseURL'],
              'Response': build_response(
                    event=event,
                    success=True,
                    reason="",
                    key_parameter_name=key_parameter_name,
                    cert_parameter_name=cert_parameter_name,
                    iam_cert_name=iam_cert_name,
                    key_parameter_arn=key_parameter_arn,
                    cert_parameter_arn=cert_parameter_arn,
                    iam_cert_arn=iam_cert_arn
              )
            }
        }
        sfn.start_execution(
            stateMachineArn=os.environ['RENEW_CERTIFICATES_STATE_MACHINE_ARN'],
            input=json.dumps(data)
        )
        # **IMPORTANT NOTE**: Do not send the response to CloudFormation yet.
        #                     The state machine will do it when it is finished
        #                     renewing all the dependent certificates, which
        #                     can take a significant amount of time if there
        #                     are many.
    else:
        # Certificate successfully created/renewed, and we have nothing else to
        # do
        send_response(
                event=event,
                success=True,
                reason="Certificate successfully created/renewed",
                key_parameter_name=key_parameter_name,
                cert_parameter_name=cert_parameter_name,
                iam_cert_name=iam_cert_name,
                key_parameter_arn=key_parameter_arn,
                cert_parameter_arn=cert_parameter_arn,
                iam_cert_arn=iam_cert_arn
        )


def delete_certificate(event):
    physical_id = event['PhysicalResourceId']
    print(f"Deleting certificate; physical_id: {physical_id}")
    # Parse the physical id to get the key and certificate SSM parameter names
    try:
        key_parameter_name, cert_parameter_name, iam_cert_name = physical_id.split(",")
    except ValueError:
        key_parameter_name = ""
        cert_parameter_name = ""
        iam_cert_name = ""
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
    if iam_cert_name:
        iam = boto3.client("iam")
        try:
            iam.delete_server_certificate(ServerCertificateName=iam_cert_name)
        except iam.exceptions.NoSuchEntityException as e:
            # Already deleted by the previous update
            pass
    send_response(
            event=event,
            success="True",
            reason="Certificate successfully deleted",
            iam_cert_name=iam_cert_name,
            key_parameter_name=key_parameter_name,
            cert_parameter_name=cert_parameter_name
    )


def build_response(
        event,
        success: bool,
        reason: str,
        key_parameter_name="",
        cert_parameter_name="",
        iam_cert_name="",
        key_parameter_arn="",
        cert_parameter_arn="",
        iam_cert_arn=""
    ):
    physical_id = ",".join([key_parameter_name, cert_parameter_name, iam_cert_name])
    response = {
        'Status': "SUCCESS" if success else "FAILED",
        'Reason': reason,
        'StackId': event['StackId'],
        'RequestId': event['RequestId'],
        'LogicalResourceId': event['LogicalResourceId'],
        'PhysicalResourceId': physical_id,
        'Data': {
            'KeyParameterArn': key_parameter_arn,
            'CertParameterArn': cert_parameter_arn,
            'KeyParameterName': key_parameter_name,
            'CertParameterName': cert_parameter_name,
            'IamCertArn': iam_cert_arn
        }
    }
    return response


def send_response(
        event,
        success: bool,
        reason: str,
        key_parameter_name="",
        cert_parameter_name="",
        iam_cert_name="",
        key_parameter_arn="",
        cert_parameter_arn="",
        iam_cert_arn=""
    ):
    response = build_response(
            event=event,
            success=success,
            reason=reason,
            key_parameter_name=key_parameter_name,
            cert_parameter_name=cert_parameter_name,
            iam_cert_name=iam_cert_name,
            key_parameter_arn=key_parameter_arn,
            cert_parameter_arn=cert_parameter_arn,
            iam_cert_arn=iam_cert_arn
    )
    print(f"Returning response {response}")
    headers = {
        'Content-Type': ""
    }
    body = json.dumps(response)
    requests.put(event['ResponseURL'], headers=headers, data=body)
