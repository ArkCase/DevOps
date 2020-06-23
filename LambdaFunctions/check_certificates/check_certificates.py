#!/usr/bin/env python3

from anytree import NodeMixin, RenderTree, LevelOrderIter
import boto3
import botocore
import cryptography
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa, dsa
from cryptography import x509
from cryptography.x509.oid import NameOID, ExtensionOID
import datetime
import json


def handler(event, context):
    """
    **IMPORTANT**: Make sure you give enough RAM to this function as all
                   the certificates will be loaded in RAM to compute their
                   dependencies and build a hierarchical tree.

    This Lambda function can operate in two different modes depending on its
    arguments:
      1. "Cascade" mode: If a certificate ARN is provided as input, it will
         build a list of dependent certificates. The goal here is to ensure
         that when a CA certificate is renewed, all certificates that
         ultimately depend on it are also renewed.
      2. "Renewal" mode: If no certificate ARN is provided as input, it will
         build a list of certificates that approaching expiry and requires
         renewal. The list will also include any dependent certificate.

    In either case, the list is saved in an S3 bucket.

    The input event must look like this:

        {
            # List of paths to scan in the Parameter Store; mandatory
            "CertParametersPaths": [ "/arkcase/pki/certs" ],

            # S3 bucket where to save the output; mandatory
            "S3Bucket": "XYZ",

            # ARN of the certificate that has just be renewed; this field is
            # optional and will operate the Lambda function in "cascade" mode;
            # if this field is absent, the Lambda function will work in
            # "renewal" mode.
            "ParentCertParameterArn": "arn:aws:...",

            # Number of days to expiry to trigger a renewal; this field is
            # mandatory for "renewal" mode, and ignored in "cascade" mode.
            "DaysToExpiryToTriggerRenewal": 14
        }

    This Lambda function returns something like this:

        {
          "S3Key": "XYZ"  # S3 key to the file containing the list; the content will be in JSON format
        }
    """

    print(f"Received event: {event}")
    s3key = handle_request(event)
    response = {
        'Success': True,
        'Reason': "Success",
        'S3Key': s3key
    }
    return response


class Certificate(NodeMixin):
    def __init__(
            self,
            cert_parameter_arn,
            cert_parameter_name,
            key_parameter_name,
            ca_key_parameter_name,
            ca_cert_parameter_name,
            cert,
            parent=None,
            children=None
    ):
        self.cert_parameter_arn = cert_parameter_arn
        self.cert_parameter_name = cert_parameter_name
        self.key_parameter_name = key_parameter_name
        self.ca_key_parameter_name = ca_key_parameter_name
        self.ca_cert_parameter_name = ca_cert_parameter_name
        self.cert = cert
        self.parent = parent
        if children:
            self.children

    def __repr__(self):
        return f"<Certificate({self.cert_parameter_name})>"


def make_certificate_from_parameter(parameter):
    """Take the `parameter` input, which must be from SSM `GetParameter()` or
    equivalent, and build a certificate object from that. The returned
    certificate object won't be part of a tree.
    """
    # Load this certificate
    cert_parameter_arn = parameter['ARN']
    cert_parameter_name = parameter['Name']
    cert_value = parameter['Value']
    cert = x509.load_pem_x509_certificate(
        cert_value.encode('utf8'),
        backend=default_backend()
    )

    # Inspect `dnQualifier` attributes for this certificate
    key_parameter_name = None
    ca_key_parameter_name = None
    ca_cert_parameter_name = None
    attributes = cert.subject.get_attributes_for_oid(NameOID.DN_QUALIFIER)
    for attribute in attributes:
        name, value = attribute.value.split(":", 1)
        if name == "key":
            key_parameter_name = value
        elif name == "cakey":
            ca_key_parameter_name = value
        elif name == "cacert":
            ca_cert_parameter_name = value
        else:
            print(f"WARNING: Unknown dnQualifier attribute '{name}' for certificate {cert_parameter_name}; ignored")
    if not key_parameter_name:
        raise KeyError(f"dnQualifier doesn't contain the key parameter name for certificate {cert_parameter_name}")

    return Certificate(
        cert_parameter_arn=cert_parameter_arn,
        cert_parameter_name=cert_parameter_name,
        key_parameter_name=key_parameter_name,
        ca_key_parameter_name=ca_key_parameter_name,
        ca_cert_parameter_name=ca_cert_parameter_name,
        cert=cert
    )


def find_certificate_by_arn(certificates, arn):
    for certificate in certificates:
        if certificate.cert_parameter_arn == arn:
            return certificate
    raise KeyError(f"Certificate not found: {arn}")


def find_certificate_by_name(certificates, name):
    for certificate in certificates:
        if certificate.cert_parameter_name == name:
            return certificate
    raise KeyError(f"Certificate not found: {name}")


def handle_request(event):
    # Fetch all the parameters containing the certificates
    cert_parameters_paths = event['CertParametersPaths']
    ssm = boto3.client("ssm")
    parameters = []
    for path in cert_parameters_paths:
        parameters += collect_cert_parameters(ssm, path)

    # Build a list of certificates to inspect
    certificates = []
    for parameter in parameters:
        certificate = make_certificate_from_parameter(parameter)
        certificates.append(certificate)

    # Get the list of certificates to renew according to the requested mode of
    # operation
    if 'ParentCertParameterArn' in event:
        result = cascade(
            ssm,
            certificates,
            event['ParentCertParameterArn']
        )
    else:
        result = check_renewals(
            ssm,
            certificates,
            int(event['DaysToExpiryToTriggerRenewal'])
        )

    # Save the certificate list in S3
    output = serialize(ssm, result)
    timestamp = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    s3key = "list of certificates to renew " + timestamp
    content = json.dumps(output, indent=2)
    print(content)  # XXX
    # TODO

    return s3key


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


def cascade(ssm, certificates, parent_cert_parameter_arn):
    parent_certificate = find_certificate_by_arn(certificates, parent_cert_parameter_arn)

    # Build a tree rooted on the parent certificate
    build_tree(certificates, parent_certificate)
    # print(RenderTree(parent_certificate))

    result = [certificate for certificate in LevelOrderIter(parent_certificate)]
    print(f"cascade result: {result}")
    return result


def check_renewals(ssm, certificates, days_to_expiry_to_trigger_renewal):
    # TODO
    return []


def build_tree(certificates, root_certificate):
    root_certificate_name = root_certificate.cert_parameter_name
    for certificate in certificates:
        if certificate.ca_cert_parameter_name == root_certificate_name:
            certificate.parent = root_certificate
            # Recurse down this certificate to build the tree
            build_tree(certificates, certificate)


def serialize(ssm, certificates):
    """Serialize a list of `Certificate` objects in a list of dictionaires
    that can be turned into JSON.
    """
    output = []
    for certificate in certificates:
        # Inspect private key to determine key type and size
        key_parameter_name = certificate.key_parameter_name
        cert_parameter_name = certificate.cert_parameter_name
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

        # Calculate validity duration
        cert = certificate.cert
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

        # Build serialized item

        item = {
            'KeyType': key_type,
            'KeySize': key_size,
            'ValidityDays': validity_days,
        }

        add_subject_attribute_if_present(item, 'CountryName', cert.subject, NameOID.COUNTRY_NAME)
        add_subject_attribute_if_present(item, 'StateOrProvinceName', cert.subject, NameOID.STATE_OR_PROVINCE_NAME)
        add_subject_attribute_if_present(item, 'LocalityName', cert.subject, NameOID.LOCALITY_NAME)
        add_subject_attribute_if_present(item, 'OrganizationName', cert.subject, NameOID.ORGANIZATION_NAME)
        add_subject_attribute_if_present(item, 'OrganizationalUnitName', cert.subject, NameOID.ORGANIZATIONAL_UNIT_NAME)
        add_subject_attribute_if_present(item, 'EmailAddress', cert.subject, NameOID.EMAIL_ADDRESS)

        try:
            basic_constraints = cert.extensions.get_extension_for_oid(ExtensionOID.BASIC_CONSTRAINTS)
            tmp = {
                'Critical': basic_constraints.critical,
                'CA': basic_constraints.value.ca
            }
            if basic_constraints.value.path_length is not None:
                tmp['PathLength'] = basic_constraints.value.path_length
            item['BasicConstraints'] = tmp
        except x509.ExtensionNotFound:
            pass

        try:
            key_usage = cert.extensions.get_extension_for_oid(ExtensionOID.KEY_USAGE)
            tmp = {
                'Critical': key_usage.critical
            }
            usages = []
            if key_usage.value.digital_signature:
                usages.append("DigitalSignature")
            if key_usage.value.content_commitment:
                usages.append("ContentCommitment")
            if key_usage.value.key_encipherment:
                usages.append("KeyEncipherment")
            if key_usage.value.data_encipherment:
                usages.append("DataEncipherment")
            if key_usage.value.key_cert_sign:
                usages.append("KeyCertSign")
            if key_usage.value.crl_sign:
                usages.append("CrlSign")
            if key_usage.value.key_agreement:
                usages.append("KeyAgreement")
                # NB: `encipher_only` and `decipher_only` are present only if
                #     `key_agreement` is set to `True`
                if key_usage.value.encipher_only:
                    usages.append("EncipherOnly")
                if key_usage.value.decipher_only:
                    usages.append("DecipherOnly")
            tmp['Usages'] = usages
            item['KeyUsage'] = tmp
        except x509.ExtensionNotFound:
            pass

        if certificate.ca_key_parameter_name:
            item['SelfSigned'] = False
            item['CaKeyParameterName'] = certificate.ca_key_parameter_name
            item['CaCertParameterName'] = certificate.ca_cert_parameter_name
        else:
            item['SelfSigned'] = True

        item['KeyParameterName'] = key_parameter_name
        item['CertParameterName'] = cert_parameter_name
        item['KeyTags'] = key_tags
        item['CertTags'] = cert_tags

        # Add this item to the list
        output.append(item)
    return output


def add_subject_attribute_if_present(item, key, subject, name_oid):
    attributes = subject.get_attributes_for_oid(name_oid)
    if attributes:
        item[key] = attributes[0].value


#    for parameter in parameters:
#        # Load this certificate
#        cert_parameter_name = parameter['Name']
#        cert_value = parameter['Value']
#        cert = x509.load_pem_x509_certificate(
#            cert_value.encode('utf8'),
#            backend=default_backend()
#        )
#
#        # Check if it is close to expiry
#        remaining_delta = cert.not_valid_after - datetime.datetime.utcnow()
#        remaining_days = remaining_delta.days
#        if remaining_days > renew_before_days:
#            print(f"Certificate {cert_parameter_name} has {remaining_days} left before expiry, no need for renewal")
#            continue
#
#        print(f"Certificate {cert_parameter_name} is close to expiry (only {remaining_days} left, min {renew_before_days}); renewing now")
#
#
#        print(f"Renewing certificate {cert_parameter_name}")
#        create_or_renew_cert(
#            key_type=key_type,
#            key_size=key_size,
#            validity_days=validity_days,
#            subject=cert.subject,
#            extensions=cert.extensions,
#            ca_key_parameter_name=ca_key_parameter_name,
#            ca_cert_parameter_name=ca_cert_parameter_name,
#            cert_parameters_paths=cert_parameters_paths,
#            key_parameter_name=key_parameter_name,
#            cert_parameter_name=cert_parameter_name,
#            key_tags=key_tags,
#            cert_tags=cert_tags
#        )
