import os
import traceback
import boto3
import botocore
import json
import requests


def handler(event, context):
    """
    Create a Secrets Manager secret. This is a replacement for
    `AWS::SecretsManager::Secret` because it has a bug: `ExcludePunctuation`
    does't work consistently.

    The event received has the following pattern (the fields are mandatory
    unless marked as "optional"):

        {
          "RequestType": "Create",  # Or "Update" or "Delete"
          "ResponseURL": "https://pre-signed-s3-url-for-response",
          "StackId": "arn:aws:cloudformation:us-west-2:123456789012:stack/stack-name/guid",
          "RequestId": "unique id for this request",
          "ResourceType": "Custom::Secret",   # or whatever
          "LogicalResourceId": "MySecret",    # or whatever
          "ResourceProperties": {
            "Name": "ABC",                      # Friendly name for the secret; optional
            "Description": "This is a secret",  # Free-form description; optional
            "GenerateSecretString": {           # Generate a random password; optional
              "ExcludeCharacters": "{}[]",      # Characters to exclude; optional
              "ExcludeLowercase": False,        # Optional, default to `False`
              "ExcludeNumbers": True,           # Optional, default to `False`
              "ExcludePunctuation": True,       # Optional, default to `False`
              "ExcludeUppercase": False,        # Optional, default to `False`
              "GenerateStringKey": "password",  # JSON key name to add the generated password; optional, default to "password"
              "IncludeSpace": False,            # Optional, default to `False`
              "PasswordLength": 42,             # Password length; optional
              "RequireEachIncludedType": True,  # Optional, default to `True`
              "SecretStringTemplate": '{"username": "bob}'  # JSON template where to insert the password;
                                                            # optional, if omitted, just the password will be used
                                                            # in the secret value
            },
            "KmsKeyId": "XYZ",  # ARN, Key ID, or alias of AWS KMS customer master key to use to encrypt the secret; optional
            "SecretString": "XXX",   # Secret text string; optional, conflicts with `GenerateSecretString`

            "Tags": [  # Tags for the secret, optional
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
        }

    The returned physical ID will be the ARN of the secret.
    """
    print(f"Received event: {event}")
    try:
        handle_request(event)
    except Exception as e:
        traceback.print_exc()
        send_response(event, False, str(e))


def handle_request(event):
    secretsmanager = boto3.client("secretsmanager")
    request_type = event['RequestType']
    print(f"Request type: {request_type}")
    if request_type == "Create" or request_type == "Update":
        arn = upsert_secret(secretsmanager, event)
    elif request_type == "Delete":
        arn = delete_secret(secretsmanager, event)
    else:
        raise ValueError(f"Invalid request type: {request_type}")
    send_response(event, True, "Success", arn)


def upsert_secret(secretsmanager, event):
    args = event['ResourceProperties']
    name = args.get('name')
    description = args.get('Description')
    generate_secret_string = args.get('GenerateSecretString')
    kms_key_id = args.get('KmsKeyId')
    secret_string = args.get('SecretString')
    tags = args.get('Tags')

    if not name:
        # Generate a unique name similar to CloudFormation
        response = secretsmanager.get_random_password(
            PasswordLength=12,
            ExcludePunctuation=True
        )
        name = event['LogicalResourceId'] + "-" + response['RandomPassword']
        print(f"Using generated name: {name}")

    if not secret_string:
        if not generate_secret_string:
            raise ValueError(f"Either `SecretString` or `GenerateSecretString` must be specified")
        print(f"`SecretString` not set, generating random password")
        password = generate_password(secretsmanager, generate_secret_string)
        if 'SecretStringTemplate' in generate_secret_string:
            # Add the password to the template
            template = json.loads(generate_secret_string['SecretStringTemplate'])
            key = generate_secret_string['GenerateStringKey']
            template[key] = password
            secret_string = json.dumps(template)
        else:
            # No template: use the password as the secret string directly
            secret_string = password

    kwargs = {
        'SecretString': secret_string
    }
    if description:
        kwargs['Description'] = description
    if kms_key_id:
        kwargs['KmsKeyId'] = kms_key_id

    if event['RequestType'] == "Create":
        kwargs['Name'] = name
        response = secretsmanager.create_secret(**kwargs)
        arn = response['ARN']
    else:
        arn = event['PhysicalResourceId']
        kwargs['SecretId'] = arn
        secretsmanager.update_secret(**kwargs)

    response = secretsmanager.describe_secret(SecretId=arn)
    old_tags = response.get('Tags', [])
    tag_keys = [tag['Key'] for tag in old_tags]
    if tag_keys:
        secretsmanager.untag_resource(SecretId=arn, TagKeys=tag_keys)
    if tags:
        secretsmanager.tag_resource(SecretId=arn, Tags=tags)
    print(f"Successfully created/updated secret {arn}")
    return arn


def delete_secret(secretsmanager, event):
    arn = event['PhysicalResourceId']
    secretsmanager.delete_secret(
        SecretId=arn,
        ForceDeleteWithoutRecovery=True
    )
    return arn


def send_response(event, success: bool, reason: str, arn=""):
    response = {
        'Status': "SUCCESS" if success else "FAILED",
        'Reason': reason,
        'StackId': event['StackId'],
        'RequestId': event['RequestId'],
        'LogicalResourceId': event['LogicalResourceId'],
        'PhysicalResourceId': arn,
    }
    print(f"Returning response {response}")
    headers = {
        'Content-Type': ""
    }
    body = json.dumps(response)
    requests.put(event['ResponseURL'], headers=headers, data=body)


def generate_password(secretsmanager, params):
    # NB: Keep in mind that CloudFormation transforms all properties into
    #     strings
    kwargs = {}
    if 'PasswordLength' in params:
        kwargs['PasswordLength'] = int(params['PasswordLength'])
    if 'ExcludeCharacters' in params:
        kwargs['ExcludeCharacters'] = params['ExcludeCharacters']
    if 'ExcludeNumbers' in params:
        kwargs['ExcludeNumbers'] = params['ExcludeNumbers'].lower() == "true"
    if 'ExcludePunctuation' in params:
        kwargs['ExcludePunctuation'] = params['ExcludePunctuation'].lower() == "true"
    if 'ExcludeUppercase' in params:
        kwargs['ExcludeUppercase'] = params['ExcludeUppercase'].lower() == "true"
    if 'ExcludeLowercase' in params:
        kwargs['ExcludeLowercase'] = params['ExcludeLowercase'].lower() == "true"
    if 'IncludeSpace' in params:
        kwargs['IncludeSpace'] = params['IncludeSpace'].lower() == "true"
    if 'RequireEachIncludedType' in params:
        kwargs['RequireEachIncludedType'] = params['RequireEachIncludedType'].lower() == "true"
    print(f"Generating random password; arguments: {kwargs}")
    response = secretsmanager.get_random_password(**kwargs)
    return response['RandomPassword']
