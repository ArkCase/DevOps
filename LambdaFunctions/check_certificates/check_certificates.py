#!/usr/bin/env python3

import os
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

    The following environment variables must be defined:
      - CERT_PARAMETERS_PATHS: A colon-separated list of paths to scan in
        the Parameter Store
      - HOW_MANY_DAYS_LEFT_BEFORE_RENEWING: Number of days to expiry before
        which a certificate will be renewed
      - S3_BUCKET: Name of the S3 bucket where to save temporary data and
        also the output of this function

    The input event must look like this:

        {
            # ARN of the certificate that has just be renewed; this field is
            # optional and will operate the Lambda function in "cascade" mode;
            # if this field is absent, the Lambda function will work in
            # "renewal" mode.
            "ParentCertParameterArn": "arn:aws:..."
        }

    This Lambda function returns something like this:

        {
          "S3Bucket": "XYZ",  # S3 bucket where the output file is located
          "S3Key": "XYZ"      # S3 key to the output file; the content will be in JSON
        }

    In actuality, a few more fields will be returned but are relevant only
    when the `check_certificates` Lambda function is called from the
    `renew_certificates` state machine.
    """

    print(f"Received event: {event}")
    s3key, count = handle_request(event)
    response = {
        'S3Bucket': os.environ['S3_BUCKET'],
        'S3Key': s3key,
        'Count': count,
        'Index': 0,
        'IsFinished': False
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

        # Determine whether this certificate is a CA or not
        try:
            basic_constraints = cert.extensions.get_extension_for_oid(ExtensionOID.BASIC_CONSTRAINTS)
            self.is_ca = basic_constraints.value.ca
        except x509.ExtensionNotFound:
            self.is_ca = False

        # Check if this certificate is close to expiry
        remaining_delta = cert.not_valid_after - datetime.datetime.utcnow()
        remaining_days = remaining_delta.days
        self.renewal_needed = remaining_days <= int(os.environ['HOW_MANY_DAYS_LEFT_BEFORE_RENEWING'])

        # NodeMixin stuff
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
    cert_parameters_paths = os.environ['CERT_PARAMETERS_PATHS'].split(":")
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
            int(os.environ['HOW_MANY_DAYS_LEFT_BEFORE_RENEWING'])
        )

    # Save the certificate list in S3
    output = serialize(ssm, result)
    timestamp = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    s3key = "list of certificates to renew " + timestamp + ".json"
    content = json.dumps(output, indent=2)
    s3 = boto3.client("s3")
    s3.put_object(
        Bucket=os.environ['S3_BUCKET'],
        Key=s3key,
        ContentType="application/json",
        Body=content
    )
    return s3key, len(output)


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

    # Build the list of certificates to renew
    result = [certificate for certificate in LevelOrderIter(parent_certificate)]
    # print(f"cascade result: {result}")
    return result


def check_renewals(ssm, certificates, how_many_days_left_before_renewing):
    # Make a list of root (i.e. self-signed) certificates
    root_certificates = []
    for certificate in certificates:
        if certificate.cert.subject == certificate.cert.issuer:
            # This is a self-signed certificate
            if certificate.is_ca:
                print(f"Found root certificate: {certificate.cert_parameter_name}")
                root_certificates.append(certificate)
            else:
                print(f"WARNING: Certificate {certificate.cert_parameter_name} is self-signed but is marked as not being a CA; ignored")

    # Build trees for each root certificate
    for root_certificate in root_certificates:
        build_tree(certificates, root_certificate)
        # print(RenderTree(root_certificate))

    # Certificates have already been checked whether they are close to expiry
    # in their constructors. We now just need to propagate CA that are to be
    # renewed to all dependent certificates.
    for root_certificate in root_certificates:
        for certificate in LevelOrderIter(root_certificate):
            if certificate.is_ca and certificate.renewal_needed:
                print(f"Certificate {certificate.cert_parameter_name} is due for renewal and is a CA; propagating to dependent certificates")
                for dependent_certificate in LevelOrderIter(certificate):
                    dependent_certificate.renewal_needed = True

    # Build the list of certificates to renew
    result = []
    for root_certificate in root_certificates:
        result += [certificate for certificate in LevelOrderIter(root_certificate) if certificate.renewal_needed]
    return result


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
