import boto3
import botocore
import json
from libarkcert import create_or_renew_cert


def handler(event, context):
    """Renew the given certificate.

    NB: This Lambda function is meant to be part of the `renew_certificates`
        state machine.

    The input `event` should look like this:

        {
          "CertList": {
            "S3Bucket": "XYZ",  # Bucket that contains the list of certificates to renew
            "S3Key": "XYZ",     # Key to the JSON file that contains the list of certificates to renew
            "Count": 17         # Length of the above list
          },
          "Iter": {
            "Index": 3,          # Index in the above list of the certificate to renew
            "IsFinished": false  # Whether all the certificates have been renewed or not
          }
        }

    This Lambda function returns something like this:

        {
          "CertList": {
            "S3Bucket": "XYZ",  # Copy of the input
            "S3Key": "XYZ",     # Copy of the input
            "Count": 17         # Copy of the input
          },
          "Iter": {
            "Index": 17,        # Index of next certificate to renew
            "IsFinished": true  # Whether all the certificates have been renewed or not
          }
        }
    """

    print(f"Received event: {event}")

    # Retrieve list of certificates to renew
    s3 = boto3.client("s3")
    response = s3.get_object(
        Bucket = event['CertList']['S3Bucket'],
        Key=event['CertList']['S3Key']
    )
    data = response['Body'].read().decode('utf8')
    cert_list = json.loads(data)

    # Sanity checks
    if event['Iter']['IsFinished'] or event['Iter']['Index'] >= event['CertList']['Count']:
        print(f"Nothing to do")
        return build_output(event)

    # Renew certificate
    args = cert_list[event['Iter']['Index']]
    create_or_renew_cert(args)

    # Done
    return build_output(event)


def build_output(event):
    index = event['Iter']['Index']
    count = event['CertList']['Count']
    if index < count:
        index += 1
    else:
        index = count

    output = event
    output['Iter']['Index'] = index
    output['Iter']['IsFinished'] = index >= count
    if 'CloudFormationData' in event:
        output['CloudFormationData'] = event['CloudFormationData']
    print(f"Output: {output}")
    return output
