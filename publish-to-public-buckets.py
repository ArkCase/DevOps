#!/usr/bin/env python3

import argparse
import sys
import os
import subprocess
import boto3
import hashlib
import binascii

# Preliminaries

ap = argparse.ArgumentParser(description="Push public files to ArkCase S3 public buckets")
ap.add_argument("-m", "--skip-mariadb-rotation-lambda",
    default=False, action="store_true",
    help="Skip the MariaDB Rotation Lambda function package")
args = ap.parse_args()
print(dir(args))

if 'AWS_PROFILE' not in os.environ and not 'AWS_DEFAULT_REGION' in os.environ:
    print(f"ERROR: You must set either the `AWS_PROFILE` or the `AWS_DEFAULT_REGION` environment variable")
    sys.exit(1)

if not args.skip_mariadb_rotation_lambda:
    # Build MariaDB Lambda rotation function package
    this_path = os.path.abspath(__file__)
    this_dir = os.path.dirname(this_path)
    os.chdir(this_dir)
    print(f"Building MariaDB rotation Lambda function package")
    subprocess.check_call(["./mariadb_rotation_lambda/package.sh"])

# Push public files to public S3 buckets

regions = [
  "us-east-1",
  "us-east-2",
  "us-west-1",
  "us-west-2",
  "ca-central-1",
  "sa-east-1",
  "eu-west-1",
  "eu-west-2",
  "eu-west-3",
  "eu-central-1",
  "eu-north-1",
  "ap-south-1",
  "ap-southeast-1",
  "ap-southeast-2",
  "ap-northeast-1",
  "ap-northeast-2"
]

public_files = [
  "CloudFormation/mariadb.yml"
]

if not args.skip_mariadb_rotation_lambda:
    public_files.append("mariadb_rotation_lambda/mariadb_rotation_lambda.zip")

s3 = boto3.client("s3")

for f in public_files:
    # Read file content
    data = open(f, "rb").read()

    # Compute MD5 of local file
    md5 = hashlib.md5()
    md5.update(data)
    binsum = md5.digest()
    sum1 = binascii.hexlify(binsum).decode("ascii")

    for region in regions:
        # Get MD5 of S3 file
        bucket = "arkcase-public-" + region
        key = "DevOps/" + f
        try:
            response = s3.head_object(Bucket=bucket, Key=key)
            sum2 = response['ETag'].strip('"')
        except Exception as e:
            sum2 = ""

        # Upload file only if it is different
        # NB: If we upload the file every time, S3 will create a new version,
        #     even if the file is exactly the same, and we will be billed for
        #     storing identical versions.
        if sum1 == sum2:
            print(f"File already exist: '{bucket}/{key}'; not uploading")
        else:
            print(f"Uploading file: '{bucket}/{key}'")
            s3.put_object(Bucket=bucket, Key=key, Body=data)
