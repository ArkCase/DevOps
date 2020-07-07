import json
import requests


def handler(event, context):
    """
    Notify CloudFormation that the renewal of a CA certificate is either
    successfully completed or has failed.

    The received `event` must have the following pattern (fields are mandatory
    unless marked as optional):

        {
          "Outcome": {       # Optional; if absent, `Success` is assumed to be `false`
            "Success": true  # or `false`; optional, default to `false`
          },

          "CloudFormationData": {  # Optional; if absent, no action is taken
            "ResponseURL": "https://pre-signed-s3-url-for-response",
            "Response": {
              "StackId": "XYZ",
              "RequestId": "XYZ",
              "LogicalResourceId": "XYZ",
              "PhysicalResourceId": "XYZ",
              "Data": {
                "KeyParameterArn": "XYZ",
                "CertParameterArn": "XYZ"
              }
            }
          }
        }

    The ARNs of the private key and certificate SSM parameters will be returned
    and made available through `Fn::GetAtt`:

        !GetAtt Certificate.KeyParameterArn
        !GetAtt Certificate.CertParameterArn

    """
    print(f"Received event: {event}")
    if 'CloudFormationData' not in event:
        print(f"No CloudFormation data; nothing to do")
        return
    success = event.get('Outcome', {}).get('Success', False)
    response_url = event['CloudFormationData']['ResponseURL']
    cfn_data = event['CloudFormationData']['Response']
    response = {
        'Status': "SUCCESS" if success else "FAILED",
        'Reason': "Success" if success else "State machine failed to renew certificates; check state machine execution log",
        'StackId': cfn_data['StackId'],
        'RequestId': cfn_data['RequestId'],
        'LogicalResourceId': cfn_data['LogicalResourceId'],
        'PhysicalResourceId': cfn_data['PhysicalResourceId'],
        'Data': {
            'KeyParameterArn': cfn_data['Data']['KeyParameterArn'],
            'CertParameterArn': cfn_data['Data']['CertParameterArn']
        }
    }
    headers = {
        'Content-Type': ""
    }
    body = json.dumps(response)
    requests.put(response_url, headers=headers, data=body)
