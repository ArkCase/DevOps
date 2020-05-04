#!/usr/bin/env python3

# Required environment variables:
#   - PASSWORD_LENGTH
#   - AMAZONMQ_BROKER_ID

import boto3
import os
import json


def handler(event, context):
    arn = event['SecretId']
    version_id = event['ClientRequestToken']
    step = event['Step']
    print(f"Received event '{step}' for secret '{arn}', version '{version_id}'")

    # Sanity checks

    client = boto3.client("secretsmanager")
    metadata = client.describe_secret(SecretId=arn)
    print(f"Secret metadata: {metadata}")
    if 'RotationEnabled' in metadata and not metadata['RotationEnabled']:
        raise ValueError(f"Rotation is disabled for secret '{arn}'")

    stages = metadata['VersionIdsToStages']
    if version_id not in stages:
        raise ValueError(f"Invalid argument: version '{version_id}' doesn't exist for secret '{arn}'")

    if 'AWSCURRENT' in stages[version_id]:
        print(f"Version '{version_id}' already set as AWSCURRENT for secret '{arn}'; nothing to do")
        return

    if 'AWSPENDING' not in stages[version_id]:
        raise ValueError(f"Invalid argument: version '{version_id}' not marked as AWSPENDING for secret '{arn}'")

    # Run the action

    if step == "createSecret":
        create_secret(client, arn, version_id)
    elif step == "setSecret":
        set_secret(client, arn, version_id)
    elif step == "testSecret":
        test_secret(client, arn, version_id)
    elif step == "finishSecret":
        finish_secret(client, arn, version_id)
    else:
        raise ValueError(f"Invalid argument: Invalid step '{step}' for secret '{arn}'")


def create_secret(client, arn, version_id):
    # Check whether this step has been done already
    # NB: This can happen in case of retries
    try:
        get_secret(client, arn, "AWSPENDING", version_id)
        print(f"create_secret: Version '{version_id}' for secret '{arn}' is already marked as AWSPENDING; nothing to do")
        return
    except SecretValueNotFoundError as e:
        pass  # This is the expected behaviour

    # Use the current secret as a template to create the new secret
    secret = get_secret(client, arn, "AWSCURRENT")
    secret['username'] = alternate_username(secret['username'])
    random_password = client.get_random_password(
            PasswordLength=int(os.environ['PASSWORD_LENGTH']),
            ExcludePunctuation=True)
    secret['password'] = random_password['RandomPassword']

    # Update the pending secret with the new value
    print(f"create_secret: Saving new secret as AWSPENDING for secret '{arn}', version '{version_id}'")
    data = json.dumps(secret)
    client.put_secret_value(SecretId=arn, ClientRequestToken=version_id, SecretString=data, VersionStages=["AWSPENDING"])
    print(f"create_secret: Successfully created new username and password for secret '{arn}', version '{version_id}'")


def set_secret(client, arn, version_id):
    # Get the pending secret
    pending_secret = get_secret(client, arn, "AWSPENDING", version_id)
    username = pending_secret['username']

    # Check whether the user exist already
    mq_client = boto3.client("mq")
    broker_id = os.environ['AMAZONMQ_BROKER_ID']
    users = mq_client.list_users(BrokerId=broker_id)
    found = False
    for user in users['Users']:
        if user['Username'] == username:
            found = True
            break

    # Initiate the required change
    if found:
        print(f"set_secret: Changing password of AmazonMQ user '{username}'...")
        mq_client.update_user(
                BrokerId=broker_id,
                ConsoleAccess=False,
                Username=username,
                Password=pending_secret['password'])
        print(f"set_secret: Successfully changed the password of AmazonMQ user '{username}'")
        print(f"set_secret: **IMPORTANT**: Changes will be effective after the next maintenance window")
    else:
        print(f"set_secret: Creating AmazonMQ user '{username}'...")
        mq_client.create_user(
                BrokerId=broker_id,
                ConsoleAccess=False,
                Username=username,
                Password=pending_secret['password'])
        print(f"set_secret: Successfully created AmazonMQ user '{username}'")
        print(f"set_secret: **IMPORTANT**: Changes will be effective after the next maintenance window")


def test_secret(client, arn, version_id):
    # We can't test the secret because the AmazonMQ broker needs to reboot for
    # the changes to be effective, and we don't want to do that at random times,
    # we wait for the next maintenance window.
    pass


def finish_secret(client, arn, version_id):
    # Check whether this step has been done already, and save the current
    # version id.
    metadata = client.describe_secret(SecretId=arn)
    for iter_version_id, stages in metadata['VersionIdsToStages'].items():
        if 'AWSCURRENT' in stages:
            current_version_id = iter_version_id
            if current_version_id == version_id:
                print(f"finish_secret: Version '{version_id}' already marked as AWSCURRENT for secret '{arn}'; nothing to do")
                return
            break

    # Mark the AWSPENDING version as AWSCURRENT
    client.update_secret_version_stage(SecretId=arn, VersionStage="AWSCURRENT", MoveToVersionId=version_id, RemoveFromVersionId=current_version_id)
    print(f"finish_secret: Successfully marked version '{version_id}' as AWSCURRENT for secret '{arn}'")


class SecretValueNotFoundError(ValueError):
    pass


def get_secret(client, arn, stage, version_id=None):
    # Get the secret
    #
    # NB: We can use the `version_id` if specified. Contrary to what the boto3
    #     documentation says
    #     [here](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/secretsmanager.html#SecretsManager.Client.get_secret_value),
    #     it is possible to specify both `VersionStage` and `VersionId`, and
    #     AWS will check that both point to the same secret version; if they
    #     are not, `get_secret_value()` will raise a
    #     `client.exceptions.InvalidRequestException`.
    if version_id:
        try:
            response = client.get_secret_value(SecretId=arn, VersionStage=stage, VersionId=version_id)
        except client.exceptions.InvalidRequestException:
            raise SecretValueNotFoundError(f"get_secret: Combination (stage '{stage}' & version '{version_id}') doesn't exist for secret '{arn}'")
        except client.exceptions.ResourceNotFoundException:
            raise SecretValueNotFoundError(f"get_secret: No secret value for stage '{stage}' and version '{version_id}' for secret '{arn}'")
    else:
        try:
            response = client.get_secret_value(SecretId=arn, VersionStage=stage)
        except client.exceptions.ResourceNotFoundException:
            raise SecretValueNotFoundError(f"get_secret: No secret value for stage '{stage}' for secret '{arn}'")
    secret = json.loads(response['SecretString'])

    # Sanity checks
    for field in ['username', 'password']:
        if field not in secret:
            raise KeyError(f"get_secret: Invalid secret '{arn}': field '{field}' must be present")

    return secret


def alternate_username(username):
    # Alternate between USERNAME1 and USERNAME2
    n = len(username)
    if n == 0 or username[n-1] not in "0123456789":
        username = username + "1"
        n = len(username)
    if n > 80:
        raise ValueError(f"User name is too long (> 80 characters): '{username}'")
    if username[n-1] == "1":
        username = username[:n-1] + "2"
    else:
        username = username[:n-1] + "1"
    return username
