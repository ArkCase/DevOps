#!/usr/bin/env python3

import os
import boto3
import botocore
import traceback
import cryptography
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa, dsa
from cryptography import x509
from cryptography.x509.oid import NameOID, ExtensionOID
import datetime
from libarkcert import create_or_renew_cert

def handler(event, context):
    """Scan all certificates under the given paths and renew them if they are
    about to expire.

    Required environment variables:
      - CERT_PARAMETERS_PATHS: Comma-separated list of paths to scan in the
        Parameter Store
      - RENEW_BEFORE_DAYS: How many days in advance of the certificate expiry
        to trigger the certificate renewal

    This Lambda function returns something like this:

        {
          "Success": true,  # Or `false`
          "Reason": "bla bla bla"
        }
    """

    print(f"Received event: {event}")
    try:
        handle_request(event)
        response = {
            'Success': True,
            'Reason': "All went well"
        }
    except Exception as e:
        print(f"EXCEPTION: {str(e)}")
        traceback.print_exc()
        response = {
            'Success': False,
            'Reason': str(e)
        }
    return response


def handle_request(event):
    cert_parameters_paths = os.environ['CERT_PARAMETERS_PATHS'].split(",")
    renew_before_days = int(os.environ['RENEW_BEFORE_DAYS'])
    print(f"CERT_PARAMETERS_PATHS: {cert_parameters_paths}")
    print(f"RENEW_BEFORE_DAYS: {renew_before_days}")

    # Build a list of certificates to inspect
    ssm = boto3.client("ssm")
    parameters = []
    for path in cert_parameters_paths:
        parameters += collect_cert_parameters(ssm, path)

    for parameter in parameters:
        # Load this certificate
        cert_parameter_name = parameter['Name']
        cert_value = parameter['Value']
        cert = x509.load_pem_x509_certificate(
            cert_value.encode('utf8'),
            backend=default_backend()
        )

        # Check if it is close to expiry
        remaining_delta = cert.not_valid_after - datetime.datetime.utcnow()
        remaining_days = remaining_delta.days
        if remaining_days > renew_before_days:
            print(f"Certificate {cert_parameter_name} has {remaining_days} left before expiry, no need for renewal")
            continue

        print(f"Certificate {cert_parameter_name} is close to expiry (only {remaining_days} left, min {renew_before_days}); renewing now")
        # Inspect `dnQualifier` attributes for this certificate
        key_parameter_name = None
        ca_key_parameter_name = None
        ca_cert_parameter_name = None
        cert_parameters_paths = []
        attributes = cert.subject.get_attributes_for_oid(NameOID.DN_QUALIFIER)
        for attribute in attributes:
            name, value = attribute.value.split(":", 1)
            if name == "key":
                key_parameter_name = value
            elif name == "cakey":
                ca_key_parameter_name = value
            elif name == "cacert":
                ca_cert_parameter_name = value
            elif name == "path":
                cert_parameters_paths.append(value)
        if not key_parameter_name:
            raise KeyError(f"Missing key parameter name in dnQualifier in certificate {cert_parameter_name}")

        # Inspect private key to determine key type and size
        print(f"Fetching private key {key_parameter_name}")
        response = ssm.get_parameter(
            Name=key_parameter_name,
            WithDecryption=True
        )
        key_value = response['Parameter']['Value']
        key = serialization.load_pem_private_key(
            key_value.encode('utf8'),
            password=None,
            backend=default_backend()
        )
        if isinstance(key, rsa.RSAPrivateKey):
            key_type = "RSA"
            key_size = key.key_size
        elif isinstance(key, dsa.DSAPrivateKey):
            key_type = "DSA"
            key_size = key.key_size
        else:
            raise ValueError(f"Unhandled private key type for {cert_parameter_name}")

        validity_delta = cert.not_valid_after - cert.not_valid_before
        validity_days = validity_delta.days

        # Get tags for key and certificate parameters
        response = ssm.list_tags_for_resource(
            ResourceType="Parameter",
            ResourceId=key_parameter_name
        )
        key_tags = response['TagList']
        response = ssm.list_tags_for_resource(
            ResourceType="Parameter",
            ResourceId=cert_parameter_name
        )
        cert_tags = response['TagList']

        print(f"Renewing certificate {cert_parameter_name}")
        create_or_renew_cert(
            key_type=key_type,
            key_size=key_size,
            validity_days=validity_days,
            subject=cert.subject,
            extensions=cert.extensions,
            ca_key_parameter_name=ca_key_parameter_name,
            ca_cert_parameter_name=ca_cert_parameter_name,
            key_parameter_name=key_parameter_name,
            cert_parameter_name=cert_parameter_name,
            key_tags=key_tags,
            cert_tags=cert_tags
        )


def collect_cert_parameters(ssm, path):
    result = []
    has_more = True
    next_token = ""
    while has_more:
        # NB: AWS API doesn't allow to get more than 10 parameters at a time
        if next_token:
            response = ssm.get_parameters_by_path(
                Path=path,
                Recursive=True,
                MaxResults=10,
                NextToken=next_token
            )
        else:
            response = ssm.get_parameters_by_path(
                Path=path,
                Recursive=True,
                MaxResults=10
            )
        result += response['Parameters']
        if 'NextToken' in response:
            next_token = response['NextToken']
        else:
            has_more = False
    return result
