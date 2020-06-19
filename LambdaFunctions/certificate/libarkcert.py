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
        ca_key_parameter_name, ca_cert_parameter_name, cert_parameters_paths,
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
    try:
        extension = cert.extensions.get_extension_for_oid(ExtensionOID.BASIC_CONSTRAINTS)
        is_ca = extension.value.ca
    except x509.ExtensionNotFound:
        is_ca = False
    if is_ca:
        if not cert_parameters_paths:
            raise KeyError(f"This certificate {cert_parameter_name} is a CA but no `CertParametersPaths` provided")
        print(f"This certificate {cert_parameter_name} is a CA; propagating renewals to dependent certificates")
        cascade(ssm, cert_parameters_paths, key_parameter_name)
    else:
        print(f"This certificate {cert_parameter_name} is not a CA; no need to search for dependent certificates to renew")
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


def cascade(ssm, paths, parent_key_parameter_name):
    # Build a list of certificates to inspect
    parameters = []
    for path in paths:
        parameters += collect_cert_parameters(ssm, path)

    for parameter in parameters:
        # Load this certificate
        cert_parameter_name = parameter['Name']
        cert_value = parameter['Value']
        cert = x509.load_pem_x509_certificate(
            cert_value.encode('utf8'),
            backend=default_backend()
        )

        # Inspect `dnQualifier` attributes for this certificate and check
        # whether it has been signed by the parent key, in which case it will
        # need to be renewed.
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
        if not ca_key_parameter_name:
            print(f"Certificate {cert_parameter_name} is self-signed; no renewal needed")
            continue
        if ca_key_parameter_name != parent_key_parameter_name:
            print(f"Certificate {cert_parameter_name} has been signed by another CA: {ca_key_parameter_name}; no renewal needed")
            continue

        # This certificate needs renewal
        print(f"Certificate {cert_parameter_name} has been signed by {ca_key_parameter_name}; renewal needed")

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
            validity_days=validity_delta.days,
            subject=cert.subject,
            extensions=cert.extensions,
            ca_key_parameter_name=ca_key_parameter_name,
            ca_cert_parameter_name=ca_cert_parameter_name,
            cert_parameters_paths=cert_parameters_paths,
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
                MaxResults=10,
                Recursive=True
            )
        result += response['Parameters']
        next_token = response.get('NextToken', "")
        if not next_token:
            has_more = False
    return result
