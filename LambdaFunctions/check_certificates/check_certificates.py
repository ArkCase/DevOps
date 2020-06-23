#!/usr/bin/env python3

from anytree import NodeMixin, RenderTree
import boto3
import botocore
import cryptography
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa, dsa
from cryptography import x509
from cryptography.x509.oid import NameOID, ExtensionOID
import datetime


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
            parent=None,
            children=None
    ):
        self.cert_parameter_arn = cert_parameter_arn
        self.cert_parameter_name = cert_parameter_name
        self.key_parameter_name = key_parameter_name
        self.ca_key_parameter_name = ca_key_parameter_name
        self.ca_cert_parameter_name = ca_cert_parameter_name
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
        cert_parameter_arn,
        cert_parameter_name,
        key_parameter_name,
        ca_key_parameter_name,
        ca_cert_parameter_name
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

    # Perform the requested operation
    if 'ParentCertParameterArn' in event:
        s3key = cascade(
            ssm,
            certificates,
            event['ParentCertParameterArn']
        )
    else:
        s3key = check_renewals(
            ssm,
            certificates,
            int(event['DaysToExpiryToTriggerRenewal'])
        )
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
    # XXX
    print(RenderTree(parent_certificate))


def check_renewals(ssm, certificates, days_to_expiry_to_trigger_renewal):
    pass  # TODO


def build_tree(certificates, root_certificate):
    root_certificate_name = root_certificate.cert_parameter_name
    for certificate in certificates:
        if certificate.ca_cert_parameter_name == root_certificate_name:
            certificate.parent = root_certificate
            # Recurse down this certificate to build the tree
            build_tree(certificates, certificate)


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
#        # Inspect `dnQualifier` attributes for this certificate
#        key_parameter_name = None
#        ca_key_parameter_name = None
#        ca_cert_parameter_name = None
#        cert_parameters_paths = []
#        attributes = cert.subject.get_attributes_for_oid(NameOID.DN_QUALIFIER)
#        for attribute in attributes:
#            name, value = attribute.value.split(":", 1)
#            if name == "key":
#                key_parameter_name = value
#            elif name == "cakey":
#                ca_key_parameter_name = value
#            elif name == "cacert":
#                ca_cert_parameter_name = value
#            elif name == "path":
#                cert_parameters_paths.append(value)
#        if not key_parameter_name:
#            raise KeyError(f"Missing key parameter name in dnQualifier in certificate {cert_parameter_name}")
#
#        # Inspect private key to determine key type and size
#        print(f"Fetching private key {key_parameter_name}")
#        response = ssm.get_parameter(
#            Name=key_parameter_name,
#            WithDecryption=True
#        )
#        key_value = response['Parameter']['Value']
#        key = serialization.load_pem_private_key(
#            key_value.encode('utf8'),
#            password=None,
#            backend=default_backend()
#        )
#        if isinstance(key, rsa.RSAPrivateKey):
#            key_type = "RSA"
#            key_size = key.key_size
#        elif isinstance(key, dsa.DSAPrivateKey):
#            key_type = "DSA"
#            key_size = key.key_size
#        else:
#            raise ValueError(f"Unhandled private key type for {cert_parameter_name}")
#
#        validity_delta = cert.not_valid_after - cert.not_valid_before
#        validity_days = validity_delta.days
#
#        # Get tags for key and certificate parameters
#        response = ssm.list_tags_for_resource(
#            ResourceType="Parameter",
#            ResourceId=key_parameter_name
#        )
#        key_tags = response['TagList']
#        response = ssm.list_tags_for_resource(
#            ResourceType="Parameter",
#            ResourceId=cert_parameter_name
#        )
#        cert_tags = response['TagList']
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
