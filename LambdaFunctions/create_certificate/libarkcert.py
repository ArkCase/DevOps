import boto3
import botocore
import cryptography
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa, dsa
from cryptography import x509
from cryptography.x509.oid import NameOID, ExtensionOID
import datetime


def create_or_renew_cert(
        key_type, key_size, validity_days,
        subject, extensions,
        ca_key_parameter_name, ca_cert_parameter_name,
        key_parameter_name, cert_parameter_name, key_tags, cert_tags):
    # Check key and certificate parameter names
    if "," in key_parameter_name:
        raise ValueError(f"Key parameter name can't have commas: {key_parameter_name}")
    if "," in cert_parameter_name:
        raise ValueError(f"Certificate parameter name can't have commas: {cert_parameter_name}")

    print(f"Generating private key {key_parameter_name}")
    if key_type == "RSA":
        key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size,
            backend=default_backend()
        )
    elif key_type == "DSA":
        key = dsa.generate_private_key(
            key_size=key_size,
            backend=default_backend()
        )
    else:
        raise ValueError(f"Unsupported key type: {key_type}")
    print(f"Successfully generated private key {key_parameter_name}")

    # Get the CA private key and certificate
    ssm = boto3.client("ssm")
    if ca_key_parameter_name:
        # Sign with CA key
        ca_key, ca_cert = get_ca_parameters(ssm, ca_key_parameter_name, ca_cert_parameter_name)
        issuer = ca_cert.subject
    else:
        # Self-signed
        ca_key = None
        ca_cert = None
        issuer = subject

    print(f"Generating X.509 certificate {cert_parameter_name}")
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
        datetime.datetime.utcnow() + datetime.timedelta(days=validity_days)
    )

    for extension in extensions:
        cert = cert.add_extension(extension.value, extension.critical)

    if ca_key:
        print(f"Signing certficate {cert_parameter_name} with CA key {ca_key_parameter_name}")
        cert = cert.sign(ca_key, hashes.SHA256(), default_backend())
    else:
        print(f"Self-signing certificate {cert_parameter_name}")
        cert = cert.sign(key, hashes.SHA256(), default_backend())

    # Save the private key

    print(f"Saving private key {key_parameter_name} in Parameter Store")
    key_value = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode('utf8')

    key_parameter_arn = upsert_param(
        ssm,
        key_parameter_name,
        key_value,
        "Private key for " + cert_parameter_name,
        "SecureString",
        key_tags
    )

    # Save the certificate

    print(f"Saving certificate {cert_parameter_name} in Parameter Store")
    cert_value = cert.public_bytes(serialization.Encoding.PEM).decode('utf8')

    cert_parameter_arn = upsert_param(
        ssm,
        cert_parameter_name,
        cert_value,
        "X.509 certificate for " + cert_parameter_name,
        "String",
        cert_tags
    )

    # Propagate renewals if applicable
    print(f"Successfully generated private key and certificate; key ARN: {key_parameter_arn}, certificate ARN: {cert_parameter_arn}")
    return key_parameter_arn, cert_parameter_arn


def get_ca_parameters(ssm, ca_key_parameter_name, ca_cert_parameter_name):
    """Retrieve the CA private key and certificate"""
    print(f"Retrieving CA private key")
    response = ssm.get_parameter(
        Name=ca_key_parameter_name,
        WithDecryption=True
    )
    ca_key_value = response['Parameter']['Value']
    ca_key = serialization.load_pem_private_key(
        ca_key_value.encode('utf8'),
        password=None,
        backend=default_backend()
    )

    print(f"Retrieving CA certificate")
    response = ssm.get_parameter(Name=ca_cert_parameter_name)
    ca_cert_value = response['Parameter']['Value']
    ca_cert = x509.load_pem_x509_certificate(
        ca_cert_value.encode('utf8'),
        backend=default_backend()
    )

    return ca_key, ca_cert


def upsert_param(ssm, name: str, value: str, desc: str, param_type: str, tags: dict):
    """
    Save the parameter

    Returns: The parameter's ARN
    """
    # NB: `put_parameter()` doesn't allow `Overwrite` to be set to `True` and
    #     tags to be set as well.
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
        TagKeys=[tag['Key'] for tag in response['TagList']]
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
