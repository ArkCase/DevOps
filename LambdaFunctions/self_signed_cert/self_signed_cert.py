#!/usr/bin/env python3

import boto3
import botocore
import cryptography
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization, hashes
from cryptography import x509
from cryptography.x509.oid import NameOID
import datetime


def handler(event, context):
    """Create an RSA or DSA private key and a self-signed certificate, and
    store them in Parameter Store as secure (i.e. encrypted) parameters. Please
    note you will still need to configure the proper IAM permissions for the
    created/updated parameters yourself.

    The input `event` must look like this:

        {
            "KeyType": "RSA",  # or "DSA"
            "KeySize": 2048,

            "CountryName": "US",
            "StateOrProvinceName": "VA",
            "LocalityName": "Vienna",
            "OrganizationName": "Armedia, LLC",
            "CommonName": "arkcase.internal",
            "ValidityDays": 100,  # For how many days the certificate should be valid

            "BasicConstraints": {  # Basic constraints extension, optional
              "Critical": true,    # Whether these basic constraints are critical; optional, default to `false`
              "CA": true,          # Whether the certificate can sign certificates; optional, default to `false`
              "PathLength": 3      # Max length of the chain; optional, default to `null` (which means "no limit")
            },

            "KeyUsage": {             # Key usage extension, optional
              "Critical": true,       # Whether these key usages are critical; optional, default to `false`
              [                       # List of usages; absent means "no"
                "DigitalSignature",   # Can verify digital signatures
                "ContentCommitment",  # Non-repudiation
                "KeyEncipherment",    # Can encrypt keys
                "DataEncipherment,    # Can encrypt data
                "KeyAgreement",       # Key agreement (eg: DH)
                "KeyCertSign",        # Can sign certificates; if set, `BasicConstraints.CA` must be set to `true`
                "CrlSign",            # Can sign CRLs
                "EncipherOnly",       # Can encrypt following a key agreement
                "DecipherOnly"        # Can decrypt following a key agreement
              ]
            },

            # Name of the SSM Parameter where to save the private key
            "KeyParameterName": "my-private-key",
            # Name of the SSM Parameter where to save the certificate
            "CertParameterName": "my-cert",

            "KeyTags": {  # Tags to add to the private key parameter, optional
              "Key": "Value",
              "Key": "Value"
            },
            "CertTags": {  # Tags to add to the certificate parameter, optional
              "Key": "Value",
              "Key": "Value"
            },
        }

    This Lambda function returns something like this:

        {
            "Success": true,
            "Reason": "",
            "KeyParameterArn": "arn:aws:...",  # ARN of the Parameter Store parameter that holds the private key
            "CertParameterArn": "arn:aws:..."  # ARN of the Parameter Store parameter that holds the certificate
        }
    """

    try:
        response = handle_request(event)
    except Exception as e:
        response = {
            'Success': False,
            'Reason': str(e)
        }
    return response


def handle_request(event):
    ssm = boto3.client("ssm")

    # Generate the private key
    key_type = event['KeyType']
    if key_type == "RSA":
        key = cryptography.hazmat.primitives.asymmetric.rsa.generate_private_key(
            public_exponent=65537,
            key_size=int(event['KeySize']),
            backend=default_backend()
        )
    elif key_type == "DSA":
        key = cryptography.hazmat.primitives.asymmetric.dsa.generate_private_key(
            key_size=int(event['KeySize']),
            backend=default_backend()
        )
    else:
        raise ValueError(f"Unsupported key type: {key_type}")

    # Generate the self-signed certificate

    subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, event['CountryName']),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, event['StateOrProvinceName']),
        x509.NameAttribute(NameOID.LOCALITY_NAME, event['LocalityName']),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, event['OrganizationName']),
        x509.NameAttribute(NameOID.COMMON_NAME, event['CommonName']),
    ])

    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        subject
    ).public_key(
        key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.utcnow()
    ).not_valid_after(
        datetime.datetie.utcnow() + datetime.timedelta(days=int(event['ValidityDays']))
    )

    if 'BasicConstraints' in event:
        basic_constraints = event['BasicConstraints']
        critical = basic_constraints.get('Critical', False)
        ca = basic_constraints.get('CA', False)
        path_length = basic_constraints.get('PathLength', None)
        cert = cert.add_extension(
            x509.BasicConstraints(ca=ca, path_length=path_length),
            critical=critical
        )

    if 'KeyUsage' in event:
        key_usage = event['KeyUsage']
        critical = key_usage.get('Critical', False)
        digital_signature = key_usage.get('DigitalSignature', False)
        content_commitment = key_usage.get('ContentCommitment', False)
        key_encipherment = key_usage.get('KeyEncipherment', False)
        data_encipherment = key_usage.get('DataEncipherment', False)
        key_agreement = key_usage.get('KeyAgreement', False)
        key_cert_sign = key_usage.get('KeyCertSign', False)
        crl_sign = key_usage.get('CrlSign', False)
        encipher_only = key_usage.get('EncipherOnly', False)
        decipher_only = key_usage.get('DecipherOnly', False)
        cert = cert.add_extension(
            x509.KeyUsage(
                digital_signature=digital_signature,
                content_commitment=content_commitment,
                key_encipherment=key_encipherment,
                data_encipherment=data_encipherment,
                key_agreement=key_agreement,
                key_cert_sign=key_cert_sign,
                crl_sign=crl_sign,
                encipher_only=encipher_only,
                decipher_only=decipher_only
            ),
            critical=critical
        )

    cert = cert.sign(key, hashes.SHA256(), default_backend())

    # Save the private key

    parameter_name = event['KeyParameterName']
    key_value = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    tags = []
    if 'KeyTags' in event:
        for k, v in event['KeyTags']:
            tags.append({
                'Key': k,
                'Value': v
            })

    ssm.put_parameter(
        Name=parameter_name,
        Description="Private key for " + event['CommonName']
        Value=key_value,
        Type="SecureString",
        Overwrite=True,
        Tags=tags
    )

    response = ssm.get_parameter(Name=parameter_name)
    key_parameter_arn = response['Parameter']['ARN']

    # Save the certificate

    parameter_name = event['CertParameterName']
    cert_value = cert.public_bytes(serialization.Encoding.PEM)

    tags = []
    if 'CertTags' in event:
        for k, v in event['CertTags']:
            tags.append({
                'Key': k,
                'Value': v
            })

    ssm.put_parameter(
        Name=parameter_name,
        Description="X.509 certificate for " + event['CommonName']
        Value=cert_value,
        Type="String",
        Overwrite=True,
        Tags=tags
    )

    response = ssm.get_parameter(Name=parameter_name)
    cert_parameter_arn = response['Parameter']['ARN']

    # Build response

    return {
        'Success': True,
        'Reason': "Successfully created/updated private key and certificate for " + event['CommonName'],
        'KeyParameterArn': key_parameter_arn,
        'CertParameterArn': cert_parameter_arn
    }
