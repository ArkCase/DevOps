#!/usr/bin/env python3

import boto3
import botocore
import traceback
import cryptography
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization, hashes
from cryptography import x509
from cryptography.x509.oid import NameOID
import datetime


def handler(event, context):
    """Create an RSA or DSA private key and a certificate signed by the given
    CA (or self-signed if no CA is provided), and store them in Parameter Store
    as secure (i.e. encrypted) parameters. Please note you will still need to
    configure the proper IAM permissions for the created/updated parameters
    yourself.

    The input `event` must look like this (fields are mandatory unless marked
    as "optional"):

        {
          "KeyType": "RSA",     # Optional, can be "RSA" or "DSA", default to "RSA"
          "KeySize": 2048,      # Key size
          "ValidityDays": 100,  # For how many days the certificate should be valid

          "CountryName": "US",                 # Optional
          "StateOrProvinceName": "VA",         # Optional
          "LocalityName": "Vienna",            # Optional
          "OrganizationName": "Armedia, LLC",  # Optional
          "OrganizationalUnitName": "SecOps",  # Optional
          "EmailAddress": "bob@example.com",   # Optional
          "CommonName": "arkcase.internal",    # Optional in theory, required in practice

          "BasicConstraints": {  # Basic constraints extension, optional
            "Critical": true,    # Whether these basic constraints are critical; optional, default to `false`
            "CA": true,          # Whether the certificate can sign certificates; optional, default to `false`
            "PathLength": 3      # Max length of the chain; optional, default to `null` (which means "no limit")
          },

          "KeyUsage": {             # Key usage extension, optional
            "Critical": true,       # Whether these key usages are critical; optional, default to `false`
            "Usages": [             # List of usages; absent means "no"
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

          # Name of the parameters storing the private key and certificate of
          # the CA that will be used to sign this new certificate. If either
          # is missing, a self-signed certificate will be issued.
          "CaKeyParameterName": "XYZ",
          "CaCertParameterName": "XYZ",

          # Name of the SSM parameter where to save the private key
          "KeyParameterName": "/arkcase/pki/private/my-key",
          # Name of the SSM parameter where to save the certificate
          "CertParameterName": "/arkcase/pki/certs/my-cert",

          "KeyTags": [  # Tags for the private key parameter, optional
            {
              "Key": "tag key",
              "Value": "tag value"
            },
            {
              "Key": "tag key 2",
              "Value": "tag value 2"
            }
          ],
          "CertTags": [  # Tags for the certificate parameter, optional
            {
              "Key": "tag key",
              "Value": "tag value"
            },
            {
              "Key": "tag key 2",
              "Value": "tag value 2"
            }
          ]
        }

    This Lambda function returns something like this:

        {
          "Success": true,
          "Reason": "bla bla bla",
          "KeyParameterArn": "arn:aws:...",  # ARN of the Parameter Store parameter that holds the private key
          "CertParameterArn": "arn:aws:..."  # ARN of the Parameter Store parameter that holds the certificate
        }
    """

    try:
        key_parameter_arn, cert_parameter_arn = handle_request(event)
        if 'CommonName' in event:
            msg = "Successfully created/renewed private key and certificate for " + event['CommonName']
        else:
            msg = "Successfully created/renewed private key and certificate"
        response = {
            'Success': True,
            'Reason': msg,
            'KeyParameterArn': key_parameter_arn,
            'CertParameterArn': cert_parameter_arn
        }
    except Exception as e:
        traceback.print_exc()
        response = {
            'Success': False,
            'Reason': str(e)
        }
    return response


def handle_request(event):
    # Generate the private key
    key_type = event.get('KeyType', "RSA")
    key_size = int(event['KeySize'])
    if key_type == "RSA":
        key = cryptography.hazmat.primitives.asymmetric.rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size,
            backend=default_backend()
        )
    elif key_type == "DSA":
        key = cryptography.hazmat.primitives.asymmetric.dsa.generate_private_key(
            key_size=key_size,
            backend=default_backend()
        )
    else:
        raise ValueError(f"Unsupported key type: {key_type}")

    # Get the CA private key and certificate
    ca_key, ca_cert = get_ca_parameters(event)

    # Generate the signed certificate

    attr = []
    if 'CountryName' in event:
        attr.append(x509.NameAttribute(NameOID.COUNTRY_NAME, event['CountryName']))
    if 'StateOrProvinceName' in event:
        attr.append(x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, event['StateOrProvinceName']))
    if 'LocalityName' in event:
        attr.append(x509.NameAttribute(NameOID.LOCALITY_NAME, event['LocalityName']))
    if 'OrganizationName' in event:
        attr.append(x509.NameAttribute(NameOID.ORGANIZATION_NAME, event['OrganizationName']))
    if 'OrganizationalUnitName' in event:
        attr.append(x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, event['OrganizationalUnitName']))
    if 'EmailAddress' in event:
        attr.append(x509.NameAttribute(NameOID.EMAIL_ADDRESS, event['EmailAddress']))
    if 'CommonName' in event:
        attr.append(x509.NameAttribute(NameOID.COMMON_NAME, event['CommonName']))
    subject = x509.Name(attr)

    issuer = ca_cert.subject if ca_cert else subject

    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.utcnow()
    ).not_valid_after(
        datetime.datetime.utcnow() + datetime.timedelta(days=int(event['ValidityDays']))
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
        usages = key_usage['Usages']
        digital_signature = 'DigitalSignature' in usages
        content_commitment = 'ContentCommitment' in usages
        key_encipherment = 'KeyEncipherment' in usages
        data_encipherment = 'DataEncipherment' in usages
        key_agreement = 'KeyAgreement' in usages
        key_cert_sign = 'KeyCertSign' in usages
        crl_sign = 'CrlSign' in usages
        encipher_only = 'EncipherOnly' in usages
        decipher_only = 'DecipherOnly' in usages
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

    if ca_key:
        # Sign the certficate with the CA key
        cert = cert.sign(ca_key, hashes.SHA256(), default_backend())
    else:
        # Self-sign the certificate
        cert = cert.sign(key, hashes.SHA256(), default_backend())

    # Save the private key

    parameter_name = event['KeyParameterName']
    key_value = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode('utf8')

    if 'CommonName' in event:
        desc = "Private key for " + event['CommonName']
    else:
        desc = "Private key"
    key_parameter_arn = upsert_param(
        parameter_name,
        key_value,
        desc,
        "SecureString",
        event.get('KeyTags', [])
    )

    # Save the certificate

    parameter_name = event['CertParameterName']
    cert_value = cert.public_bytes(serialization.Encoding.PEM).decode('utf8')

    if 'CommonName' in event:
        desc = "X.509 certificate for " + event['CommonName']
    else:
        desc = "X.509 certificate"
    cert_parameter_arn = upsert_param(
        parameter_name,
        cert_value,
        desc,
        "String",
        event.get('CertTags', [])
    )

    # Done
    return key_parameter_arn, cert_parameter_arn


def get_ca_parameters(event):
    """Retrieve the CA private key and certificate"""
    if 'CaKeyParameterName' not in event or 'CaCertParameterName' not in event:
        return None, None

    ssm = boto3.client("ssm")

    response = ssm.get_parameter(
        Name=event['CaKeyParameterName'],
        WithDecryption=True
    )
    ca_key_value = response['Parameter']['Value']
    ca_key = serialization.load_pem_private_key(
        ca_key_value.encode('utf8'),
        password=None,
        backend=default_backend()
    )

    response = ssm.get_parameter(Name=event['CaCertParameterName'])
    ca_cert_value = response['Parameter']['Value']
    ca_cert = x509.load_pem_x509_certificate(
        ca_cert_value.encode('utf8'),
        backend=default_backend()
    )

    return ca_key, ca_cert


def upsert_param(name: str, value: str, desc: str, param_type: str, tags: dict):
    """
    Save the parameter

    Returns: The parameter's ARN
    """
    # NB: `put_parameter()` doesn't allow `Overwrite` to be set to `True` and
    #     tags to be set as well.
    ssm = boto3.client("ssm")
    ssm.put_parameter(
        Name=name,
        Value=value,
        Description=desc,
        Type=param_type,
        Overwrite=True
    )

    # Erase all existing tags
    response = ssm.list_tags_for_resource(
        ResourceType="Parameter",
        ResourceId=name
    )
    ssm.remove_tags_from_resource(
        ResourceType="Parameter",
        ResourceId=name,
        TagKeys=[i['Key'] for i in response['TagList']]
    )

    # Save new tags
    if tags:
        ssm.add_tags_to_resource(
            ResourceType="Parameter",
            ResourceId=name,
            Tags=tags
        )

    # Return the parameter's ARN
    response = ssm.get_parameter(Name=name)
    return response['Parameter']['ARN']
