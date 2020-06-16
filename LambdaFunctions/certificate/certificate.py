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

          # Whether this certificate should be self-signed or signed by a CA.
          # If set to `false`, you must also set the `CaKeyParameterName` and
          # `CaCertParameterName` to valid values.
          #
          # Optional; default to `false`
          "SelfSigned": false,

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

    print(f"Received event: {event}")
    try:
        key_parameter_arn, cert_parameter_arn = create_or_renew_cert(event)
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
        print(f"EXCEPTION: {str(e)}")
        traceback.print_exc()
        response = {
            'Success': False,
            'Reason': str(e)
        }
    return response


def create_or_renew_cert(args):
    # Check key and certificate parameter names
    key_parameter_name = args['KeyParameterName']
    cert_parameter_name = args['CertParameterName']
    if "," in key_parameter_name:
        raise ValueError(f"Key parameter name can't have commas: {key_parameter_name}")
    if "," in cert_parameter_name:
        raise ValueError(f"Certificate parameter name can't have commas: {cert_parameter_name}")

    print(f"Generating the private key for {cert_parameter_name}")
    key_type = args.get('KeyType', "RSA")
    key_size = int(args['KeySize'])
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
    print(f"Successfully generated a private key for {cert_parameter_name}")

    # Get the CA private key and certificate
    self_signed = args.get('SelfSigned', False)
    if self_signed:
        ca_key = None
        ca_cert = None
    else:
        ca_key, ca_cert = get_ca_parameters(args)

    # Generate the signed certificate

    print(f"Building distinguished name for {cert_parameter_name}")
    attr = []
    if 'CountryName' in args:
        attr.append(x509.NameAttribute(NameOID.COUNTRY_NAME, args['CountryName']))
    if 'StateOrProvinceName' in args:
        attr.append(x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, args['StateOrProvinceName']))
    if 'LocalityName' in args:
        attr.append(x509.NameAttribute(NameOID.LOCALITY_NAME, args['LocalityName']))
    if 'OrganizationName' in args:
        attr.append(x509.NameAttribute(NameOID.ORGANIZATION_NAME, args['OrganizationName']))
    if 'OrganizationalUnitName' in args:
        attr.append(x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, args['OrganizationalUnitName']))
    if 'EmailAddress' in args:
        attr.append(x509.NameAttribute(NameOID.EMAIL_ADDRESS, args['EmailAddress']))
    if not self_signed:
        tmp = args['CaKeyParameterName'] + "," + args['CaCertParameterName']
        attr.append(x509.NameAttribute(NameOID.DN_QUALIFIER, tmp))
    if 'CommonName' in args:
        attr.append(x509.NameAttribute(NameOID.COMMON_NAME, args['CommonName']))
    subject = x509.Name(attr)

    issuer = ca_cert.subject if ca_cert else subject

    print(f"Generating X.509 certificate for {cert_parameter_name}")
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
        datetime.datetime.utcnow() + datetime.timedelta(days=int(args['ValidityDays']))
    )

    if 'BasicConstraints' in args:
        print(f"Adding basic constraints extension")
        basic_constraints = args['BasicConstraints']
        critical = basic_constraints.get('Critical', False)
        ca = basic_constraints.get('CA', False)
        path_length = basic_constraints.get('PathLength', None)
        cert = cert.add_extension(
            x509.BasicConstraints(ca=ca, path_length=path_length),
            critical=critical
        )

    if 'KeyUsage' in args:
        print(f"Adding key usage extension")
        key_usage = args['KeyUsage']
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

    if self_signed:
        print(f"Self-signing the certificate for {cert_parameter_name}")
        cert = cert.sign(key, hashes.SHA256(), default_backend())
    else:
        print(f"Signing the certficate with the CA key for {cert_parameter_name}")
        cert = cert.sign(ca_key, hashes.SHA256(), default_backend())

    # Save the private key

    print(f"Saving the private key in Parameter Store: {key_parameter_name}")
    key_value = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode('utf8')

    if 'CommonName' in args:
        desc = "Private key for " + args['CommonName']
    else:
        desc = "Private key"
    key_parameter_arn = upsert_param(
        key_parameter_name,
        key_value,
        desc,
        "SecureString",
        args.get('KeyTags', [])
    )

    # Save the certificate

    print(f"Saving the certificate in Parameter Store: {cert_parameter_name}")
    cert_value = cert.public_bytes(serialization.Encoding.PEM).decode('utf8')

    if 'CommonName' in args:
        desc = "X.509 certificate for " + args['CommonName']
    else:
        desc = "X.509 certificate"
    cert_parameter_arn = upsert_param(
        cert_parameter_name,
        cert_value,
        desc,
        "String",
        args.get('CertTags', [])
    )

    # Done
    print(f"Successfully generated private key and certificate; key ARN: {key_parameter_arn}, certificate ARN: {cert_parameter_arn}")
    return key_parameter_arn, cert_parameter_arn


def get_ca_parameters(args):
    """Retrieve the CA private key and certificate"""
    ssm = boto3.client("ssm")

    print(f"Retrieving CA private key")
    response = ssm.get_parameter(
        Name=args['CaKeyParameterName'],
        WithDecryption=True
    )
    ca_key_value = response['Parameter']['Value']
    ca_key = serialization.load_pem_private_key(
        ca_key_value.encode('utf8'),
        password=None,
        backend=default_backend()
    )

    print(f"Retrieving CA certificate")
    response = ssm.get_parameter(Name=args['CaCertParameterName'])
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
    print(f"upsert_param: Calling ssm.put_parameter(Name={name})")
    ssm.put_parameter(
        Name=name,
        Value=value,
        Description=desc,
        Type=param_type,
        Overwrite=True
    )

    # Erase all existing tags
    print(f"upsert_param: Calling ssm.list_tags_for_resource(ResourceId={name})")
    response = ssm.list_tags_for_resource(
        ResourceType="Parameter",
        ResourceId=name
    )
    print(f"upsert_param: Calling ssm.remove_tags_from_resource(ResourceId={name})")
    ssm.remove_tags_from_resource(
        ResourceType="Parameter",
        ResourceId=name,
        TagKeys=[i['Key'] for i in response['TagList']]
    )

    # Save new tags
    if tags:
        print(f"upsert_param: Calling ssm.add_tags_to_resource(ResourceId={name})")
        ssm.add_tags_to_resource(
            ResourceType="Parameter",
            ResourceId=name,
            Tags=tags
        )

    # Return the parameter's ARN
    response = ssm.get_parameter(Name=name)
    print(f"upsert_param: Success; ARN: {response['Parameter']['ARN']}")
    return response['Parameter']['ARN']
