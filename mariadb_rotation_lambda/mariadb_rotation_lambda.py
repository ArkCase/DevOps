#!/usr/bin/env python3

import boto3
import botocore
import os
import json
import pymysql


def handler(event, context):
    arn = event['SecretId']
    version_id = event['ClientRequestToken']
    step = event['Step']
    print(f"Received event '{step}' for secret {arn}, version {version_id}")

    print(f"Getting client for secretsmanager...")
    client = boto3.client("secretsmanager", endpoint_url=os.environ['SECRETS_MANAGER_ENDPOINT'])
    print(f"Got secretsmanager client")

    # Sanity checks

    metadata = client.describe_secret(SecretId=arn)
    print(f"Secret metadata: {metadata}")
    if 'RotationEnabled' in metadata and not metadata['RotationEnabled']:
        raise ValueError(f"Rotation is disabled for secret {arn}")

    stages = metadata['VersionIdsToStages']
    if version_id not in stages:
        raise ValueError(f"Invalid argument: version {version_id} doesn't exist for secret {arn}")

    if 'AWSCURRENT' in stages[version_id]:
        print(f"Version {version_id} already set as AWSCURRENT for secret {arn}; nothing to do")
        return

    if 'AWSPENDING' not in stages[version_id]:
        raise ValueError(f"Invalid argument: version {version_id} not marked as AWSPENDING for secret {arn}")

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
        raise ValueError(f"Invalid argument: Invalid step {step} for secret {arn}")


def create_secret(client, arn, version_id):
    # Check whether this step has been done already
    try:
        get_secret(client, arn, "AWSPENDING", version_id)
        print(f"create_secret: Version {version_id} for secret {arn} is already marked as AWSPENDING; nothing to do")
        return
    except SecretValueNotFoundError as e:
        pass

    # Use the current secret as a template to create the new secret
    current_secret = get_secret(client, arn, "AWSCURRENT")
    current_secret['username'] = alternate_username(current_secret['username'])
    response = client.get_random_password(ExcludeCharacters="/@\"'\\%")
    current_secret['password'] = response['RandomPassword']

    # Update the pending secret with the new value
    data = json.dumps(current_secret)
    print(f"create_secret: Saving new secret as AWSPENDING for secret {arn}, version {version_id}")
    client.put_secret_value(SecretId=arn, ClientRequestToken=version_id, SecretString=data, VersionStages=["AWSPENDING"])
    print(f"create_secret: Successfully created new username and password for secret {arn}, version {version_id}")


def set_secret(client, arn, version_id):
    # Check whether this step has been done already
    pending_secret = get_secret(client, arn, "AWSPENDING", version_id)
    cnx = get_cnx(pending_secret)
    if cnx:
        cnx.close()
        print(f"set_secret: The AWSPENDING stage of secret {arn} has already been applied to the database; nothing to do")
        return

    # Connect to the database using the master credentials
    master_arn = pending_secret['masterarn']
    master_secret = get_secret(client, master_arn, "AWSCURRENT", is_master=True)
    print(f"set_secret: Successfully retrieved master secret {master_arn}")
    master_secret['host'] = pending_secret['host']
    cnx = get_cnx(master_secret)
    if not cnx:
        raise ValueError(f"set_secret: Failed to connect to database using master credentials")
    print(f"set_secret: Successfully connected to the database using the master secret")

    # RDS, by default, allows unsecure connections to MariaDB instances. So we
    # need to secure the master user, which is created by CloudFormation.
    # NB: We only need to do this once, but doing it every time doesn't hurt
    user = master_secret['username']
    sql = f"ALTER USER '{user}' REQUIRE SSL;"
    print(f"set_secret: Executing SQL to require SSL for master user: {user}")
    cnx.cursor().execute(sql)
    print(f"set_secret: Successfully enforced SSL for master user: {user}")

    # Update/create database user with the new (i.e. AWSPENDING) secret
    grants = os.environ['GRANTS'].replace("\n", " ")
    dbname = pending_secret['dbname']
    username = pending_secret['username']
    password = pending_secret['password']
    sql = f"GRANT {grants} ON {dbname}.* TO '{username}' IDENTIFIED BY '{password}' REQUIRE SSL;"
    print(f"set_secret: Executing SQL to grant privileges, modify password and enforce SSL for user '{username}'")
    cnx.cursor().execute(sql)
    print(f"set_secret: Successfully set username '{username}' and password in database for secret {arn}")
    cnx.close()


def test_secret(client, arn, version_id):
    # TODO: More extensive tests
    pending_secret = get_secret(client, arn, "AWSPENDING", version_id)
    cnx = get_cnx(pending_secret)
    if cnx:
        print(f"test_secret: Pending secret {arn} successfully tested")
        cnx.close()
    else:
        raise ValueError(f"test_secret: Can't connect to the database using the AWSPENDING stage of secret {arn}")


def finish_secret(client, arn, version_id):
    # Check whether this step has been done already, and save the current
    # version id.
    current_secret = get_secret(client, arn, "AWSCURRENT")
    metadata = client.describe_secret(SecretId=arn)
    for k, v in metadata['VersionIdsToStages'].items():
        if 'AWSCURRENT' in v:
            current_version_id = k
            if current_version_id == version_id:
                print(f"finish_secret: Version {version_id} already marked as AWSCURRENT for secret {arn}; nothing to do")
                return
            break

    # Mark the AWSPENDING version as AWSCURRENT
    client.update_secret_version_stage(SecretId=arn, VersionStage="AWSCURRENT", MoveToVersionId=version_id, RemoveFromVersionId=current_version_id)
    print(f"finish_secret: Successfully marked version {version_id} as AWSCURRENT for secret {arn}")

    # TODO: Notify or re-deploy the app


class SecretValueNotFoundError(ValueError):
    pass


def get_secret(client, arn, stage, version_id=None, is_master=False):
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
            raise SecretValueNotFoundError(f"Combination (stage {stage}/version {version_id}) doesn't exist for secret {arn}")
        except client.exceptions.ResourceNotFoundException:
            raise SecretValueNotFoundError(f"No secret value for stage {stage} and version {version_id} for secret {arn}")
    else:
        try:
            response = client.get_secret_value(SecretId=arn, VersionStage=stage)
        except client.exceptions.ResourceNotFoundException:
            raise SecretValueNotFoundError(f"No secret value for stage {stage} for secret {arn}")
    secret = json.loads(response['SecretString'])

    # Sanity checks
    if is_master:
        for field in ['username', 'password']:
            if field not in secret:
                raise KeyError(f"Invalid master secret {arn}: field {field} must be present")
    else:
        if 'engine' not in secret:
            raise KeyError(f"Secret {arn} doesn't have an 'engine' field")
        if secret['engine'] != "mariadb":
            raise KeyError(f"Secret {arn} engine must be 'mariadb', not '{secrets['engine']}'")
        for field in ['host', 'username', 'password', 'dbname', 'masterarn']:
            if field not in secret:
                raise KeyError(f"Invalid secret {arn}: field {field} must be present")

    return secret


def alternate_username(username):
    # Alternate between USERNAME1 and USERNAME2
    n = len(username)
    if n == 0 or username[n-1] not in "0123456789":
        username = "user1"
        n = len(username)
    if n > 80:
        raise ValueError(f"User name is too long (> 80 characters): {username}")
    if username[n-1] == "1":
        username = username[:n-1] + "2"
    else:
        username = username[:n-1] + "1"
    return username


def get_cnx(secret):
    host = secret['host']
    username = secret['username']
    password = secret['password']
    port = int(secret.get('port', 3306))
    dbname = secret.get('dbname')
    try:
        print(f"get_cnx: Trying host={host}, user={username}, port={port}, db={dbname})")
        # NB: We want to connect using SSL. PyMySQL checks the `ssl` argument
        #     and enables SSL if it's not empty. PyMySQL docs says that the
        #     `ssl` argument should look like `mysql_ssl_set()`, but we don't
        #     need any of the items it sets. So I just used a random key,
        #     `enabled`, such that the `ssl` argument is a non-empty
        #     dictionary to fool PyMySQL. It looks like it's working fine.
        cnx = pymysql.connect(host=host, user=username, passwd=password, port=port, db=dbname, connect_timeout=5, ssl={'enabled': True})
        print(f"get_cnx: Successfully connected")
        return cnx
    except pymysql.OperationalError as e:
        print(f"Can't connect to MariaDB host {host}:{port} with user {username}: {str(e)}")
        return None
