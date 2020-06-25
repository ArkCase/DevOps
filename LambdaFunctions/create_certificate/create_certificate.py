import traceback
import cryptography
from cryptography import x509
from cryptography.x509.oid import NameOID, ExtensionOID
from libarkcert import create_or_renew_cert


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

          "Cascade": true  # Renew dependent certificates; optional, default to `false`
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
        key_parameter_arn, cert_parameter_arn = handle_request(event)
        msg = "Successfully created/renewed private key and certificate for " + event['CertParameterName']
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


def handle_request(event):
    key_type = event.get('KeyType', "RSA")
    key_size = int(event['KeySize'])
    validity_days = int(event['ValidityDays'])
    self_signed = event.get('SelfSigned', False)
    if self_signed:
        ca_key_parameter_name = None
        ca_cert_parameter_name = None
    else:
        if 'CaKeyParameterName' not in event:
            raise KeyError(f"`SelfSigned` is set to `false`, but `CaKeyParameterName` is not set")
        if 'CaCertParameterName' not in event:
            raise KeyError(f"`SelfSigned` is set to `false`, but `CaCertParameterName` is not set")
        ca_key_parameter_name = event['CaKeyParameterName']
        ca_cert_parameter_name = event['CaCertParameterName']

    # Build distinguished name
    attributes = []
    add_attribute_if_present(event, 'CountryName', attributes, NameOID.COUNTRY_NAME)
    add_attribute_if_present(event, 'StateOrProvinceName', attributes, NameOID.STATE_OR_PROVINCE_NAME)
    add_attribute_if_present(event, 'LocalityName', attributes, NameOID.LOCALITY_NAME)
    add_attribute_if_present(event, 'OrganizationName', attributes, NameOID.ORGANIZATION_NAME)
    add_attribute_if_present(event, 'OrganizationalUnitName', attributes, NameOID.ORGANIZATIONAL_UNIT_NAME)
    add_attribute_if_present(event, 'EmailAddress', attributes, NameOID.EMAIL_ADDRESS)
    add_attribute_if_present(event, 'CommonName', attributes, NameOID.COMMON_NAME)

    # Use `dnQualifier` to store custom information
    value = "key:" + event['KeyParameterName']
    attributes.append(x509.NameAttribute(NameOID.DN_QUALIFIER, value))
    if ca_key_parameter_name:
        value = "cakey:" + ca_key_parameter_name
        attributes.append(x509.NameAttribute(NameOID.DN_QUALIFIER, value))
        value = "cacert:" + ca_cert_parameter_name
        attributes.append(x509.NameAttribute(NameOID.DN_QUALIFIER, value))

    subject = x509.Name(attributes)

    extensions = []

    if 'BasicConstraints' in event:
        print(f"Adding basic constraints extension")
        basic_constraints = event['BasicConstraints']
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

    if 'KeyUsage' in event:
        print(f"Adding key usage extension")
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

    key_parameter_name = event['KeyParameterName']
    cert_parameter_name = event['CertParameterName']
    key_tags = event.get('KeyTags', [])
    cert_tags = event.get('CertTags', [])

    key_parameter_arn, cert_parameter_arn = create_or_renew_cert(
        key_type=key_type,
        key_size=key_size,
        validity_days=validity_days,
        subject=subject,
        extensions=extensions,
        ca_key_parameter_name=ca_key_parameter_name,
        ca_cert_parameter_name=ca_cert_parameter_name,
        key_parameter_name=key_parameter_name,
        cert_parameter_name=cert_parameter_name,
        key_tags=key_tags,
        cert_tags=cert_tags
    )

    if is_ca and event.get('Cascade', False):
        print(f"This certificate is a CA and cascading is requested; executing state machine to renew dependent certificates")
        # TODO: kick off state machine
        pass

    return key_parameter_arn, cert_parameter_arn


def add_attribute_if_present(event, key, attributes, name_oid):
    if key in event:
        attributes.append(
            x509.NameAttribute(name_oid, event[key])
        )
