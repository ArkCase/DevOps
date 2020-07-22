import datetime
import boto3
import botocore
import cryptography
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa, dsa
from cryptography import x509
from cryptography.x509.oid import NameOID, ExtensionOID


def create_or_renew_cert(args: dict):
    """
    The `args` argument must look like this (fields are mandatory unless marked
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

          "SubjectAlternativeName": {  # Subject alternative name extension, optional
            "Critical": true,          # Whether this SAN is critical; optional, default to `false`
            "DNS": [                   # Name type; currently, the only valid value is "DNS"
              "name1.example.com",     # Alternative name
              "name2.example.com"      # Alternative name
            ]
          },

          "BasicConstraints": {  # Basic constraints extension, optional
            "Critical": True,    # Whether these basic constraints are critical; optional, default to `False`
            "CA": True,          # Whether the certificate can sign certificates; optional, default to `False`
            "PathLength": 3      # Max length of the chain; optional, default to `null` (which means "no limit")
          },

          "KeyUsage": {             # Key usage extension, optional
            "Critical": True,       # Whether these key usages are critical; optional, default to `False`
            "Usages": [             # List of usages; absent means "no"
              "DigitalSignature",   # Can verify digital signatures
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
          # If set to `False`, you must also set the `CaKeyParameterName` and
          # `CaCertParameterName` to valid values.
          #
          # Optional; default to `False`
          "SelfSigned": False,

          # Name of the SSM parameters storing the private key and certificate
          # of the CA that will be used to sign this new certificate. If
          # `SelfSigned` is set to `False`, those fields are mandatory.
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

    Returns a tuple:
        (key_parameter_arn, cert_parameter_arn, iam_cert_arn)

        Please note that `iam_cert_arn` will be an empty string is the
        certificate is a CA.
    """
    key_type = args.get('KeyType', "RSA")
    key_size = int(args['KeySize'])
    validity_days = int(args['ValidityDays'])
    self_signed = args.get('SelfSigned', False)
    if self_signed:
        ca_key_parameter_name = None
        ca_cert_parameter_name = None
    else:
        if 'CaKeyParameterName' not in args:
            raise KeyError(f"`SelfSigned` is set to `False`, but `CaKeyParameterName` is not set")
        if 'CaCertParameterName' not in args:
            raise KeyError(f"`SelfSigned` is set to `False`, but `CaCertParameterName` is not set")
        ca_key_parameter_name = args['CaKeyParameterName']
        ca_cert_parameter_name = args['CaCertParameterName']

    # Build subject name

    attributes = []
    add_attribute_if_present(args, 'CountryName', attributes, NameOID.COUNTRY_NAME)
    add_attribute_if_present(args, 'StateOrProvinceName', attributes, NameOID.STATE_OR_PROVINCE_NAME)
    add_attribute_if_present(args, 'LocalityName', attributes, NameOID.LOCALITY_NAME)
    add_attribute_if_present(args, 'OrganizationName', attributes, NameOID.ORGANIZATION_NAME)
    add_attribute_if_present(args, 'OrganizationalUnitName', attributes, NameOID.ORGANIZATIONAL_UNIT_NAME)
    add_attribute_if_present(args, 'EmailAddress', attributes, NameOID.EMAIL_ADDRESS)
    add_attribute_if_present(args, 'CommonName', attributes, NameOID.COMMON_NAME)

    # Use `dnQualifier` to store custom information
    value = "key:" + args['KeyParameterName']
    attributes.append(x509.NameAttribute(NameOID.DN_QUALIFIER, value))
    if ca_key_parameter_name:
        value = "cakey:" + ca_key_parameter_name
        attributes.append(x509.NameAttribute(NameOID.DN_QUALIFIER, value))
        value = "cacert:" + ca_cert_parameter_name
        attributes.append(x509.NameAttribute(NameOID.DN_QUALIFIER, value))

    subject = x509.Name(attributes)

    # Add extensions, if any

    extensions = []

    if 'SubjectAlternativeName' in args:
        print(f"Adding subject alternative name extension")
        san = args['SubjectAlternativeName']
        critical = san.get('Critical', False)
        names = []
        for name in san['DNS']:
            names.append(x509.DNSName(name))
        extension = x509.Extension(
            oid=ExtensionOID.SUBJECT_ALTERNATIVE_NAME,
            critical=critical,
            value=x509.SubjectAlternativeName(names)
        )
        extensions.append(extension)

    if 'BasicConstraints' in args:
        print(f"Adding basic constraints extension")
        basic_constraints = args['BasicConstraints']
        critical = basic_constraints.get('Critical', False)
        is_ca = basic_constraints.get('CA', False)
        path_length = basic_constraints.get('PathLength', None)
        extension = x509.Extension(
            oid=ExtensionOID.BASIC_CONSTRAINTS,
            critical=critical,
            value=x509.BasicConstraints(ca=is_ca, path_length=path_length)
        )
        extensions.append(extension)
    else:
        is_ca = False

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
        extension = x509.Extension(
            oid=ExtensionOID.KEY_USAGE,
            critical=critical,
            value=x509.KeyUsage(
                digital_signature=digital_signature,
                content_commitment=content_commitment,
                key_encipherment=key_encipherment,
                data_encipherment=data_encipherment,
                key_agreement=key_agreement,
                key_cert_sign=key_cert_sign,
                crl_sign=crl_sign,
                encipher_only=encipher_only,
                decipher_only=decipher_only
            )
        )
        extensions.append(extension)

    # Extract and check key and certificate parameter information
    key_parameter_name = args['KeyParameterName']
    if "," in key_parameter_name:
        raise ValueError(f"Key parameter name can't have commas: {key_parameter_name}")
    cert_parameter_name = args['CertParameterName']
    if "," in cert_parameter_name:
        raise ValueError(f"Certificate parameter name can't have commas: {cert_parameter_name}")
    key_tags = args.get('KeyTags', [])
    cert_tags = args.get('CertTags', [])

    # Generate private key
    print(f"Generating private key {key_parameter_name}: {key_type} {key_size} bits")
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

    # Generate the certificate

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

    # Save the certificate in IAM, but only if it is not a CA
    if not is_ca:
        print(f"Saving non-CA certificate {cert_parameter_name} in IAM")
        path_items = cert_parameter_name.split("/")
        cert_name = path_items.pop()
        cert_path = "/".join(path_items)

        # IAM paths must start and end with "/"
        if cert_path[0] != "/":
            cert_path = "/" + cert_path
        if not cert_path.endswith("/"):
            cert_path += "/"

        chain = ""
        chain = chain_certificate(ssm, chain, ca_cert)

        iam = boto3.client("iam")
        try:
            response = iam.upload_server_certificate(
                Path=cert_path,
                ServerCertificateName=cert_name,
                CertificateBody=cert_value,
                PrivateKey=key_value,
                CertificateChain=chain
            )
        except iam.exceptions.EntityAlreadyExistsException as e:
            print(f"Server certificate {cert_name} already exists; deleting old one")
            iam.delete_server_certificate(ServerCertificateName=cert_name)
            response = iam.upload_server_certificate(
                Path=cert_path,
                ServerCertificateName=cert_name,
                CertificateBody=cert_value,
                PrivateKey=key_value,
                CertificateChain=chain
            )

        iam_cert_arn = response['ServerCertificateMetadata']['Arn']
    else:
        print(f"Certificate {cert_parameter_name} is a CA: not saving it to IAM")
        iam_cert_arn = ""

    # Done
    print(f"Successfully generated private key and certificate; key ARN: {key_parameter_arn}, certificate ARN: {cert_parameter_arn}, IAM ARN: {iam_cert_arn}")
    return key_parameter_arn, cert_parameter_arn, iam_cert_arn


def add_attribute_if_present(event, key, attributes, name_oid):
    if key in event:
        attributes.append(
            x509.NameAttribute(name_oid, event[key])
        )


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


def chain_certificate(ssm, chain, cert):
    cert_value = cert.public_bytes(serialization.Encoding.PEM).decode('utf8')
    chain += cert_value
    if cert.subject == cert.issuer:
        return chain  # This certificate is self-signed => end of the chain

    attributes = cert.issuer.get_attributes_for_oid(NameOID.DN_QUALIFIER)
    for attribute in attributes:
        tmp = attribute.value.split(":", 1)
        if tmp[0] == "cacert":
            response = ssm.get_parameter(Name=tmp[1])
            ca_cert_value = response['Parameter']['Value']
            ca_cert = x509.load_pem_x509_certificate(
                ca_cert_value.encode('utf8'),
                backend=default_backend()
            )
            chain = chain_certificate(ssm, chain, ca_cert)
    return chain
