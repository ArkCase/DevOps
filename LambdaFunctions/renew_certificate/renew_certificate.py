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
            "S3Bucket": "XYZ",   # Bucket that contains the list of certificates to renew
            "S3Key": "XYZ",      # Key to the JSON file that contains the list of certificates to renew
            "Count": 17,         # Length of the above list
            "Index": 3,          # Index in the above list of the certificate to renew
            "IsFinished": false  # Whether all the certificates have been renewed or not
        }

    This Lambda function returns something like this:

        {
          "S3Bucket": "XYZ",  # Copy of the input
          "S3Key": "XYZ",     # Copy of the input
          "Count": 17,        # Copy of the input
          "Index": 17,        # Index of next certificate to renew
          "IsFinished": true  # Whether all the certificates have been renewed or not
        }
    """

    print(f"Received event: {event}")

    # Retrieve list of certificates to renew
    s3 = boto3.client("s3")
    response = s3.get_object(
        Bucket = event['S3Bucket'],
        Key=event['S3Key']
    )
    data = response['Body'].read().decode('utf8')
    cert_list = json.loads(data)

    # Renew certificate
    index = event['Index']
    args = cert_list[index]
    key_parameter_arn, cert_parameter_arn = create_or_renew_cert(args)

    # Done
    output = event
    index += 1
    output['Index'] = index
    output['IsFinished'] = index >= output['Count']
    print(f"Output: {output}")
    return output
