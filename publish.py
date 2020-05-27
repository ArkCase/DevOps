#!/usr/bin/env python3

import argparse
import sys
import datetime
import os
import subprocess
import re
import boto3

# Preliminaries

this_path = os.path.abspath(__file__)
this_dir = os.path.dirname(this_path)
os.chdir(this_dir)

ap = argparse.ArgumentParser(description="Push public files to ArkCase S3 public buckets")
ap.add_argument("TAG", default="dev",
    help="Package tag (dev, prod, staging, etc.); letters and numbers only")
ap.add_argument("-k", "--keep-temporary",
    default=False, action="store_true",
    help="Don't delete temporary and intermediate files")
ap.add_argument("-r", "--region",
    default=[], action="append",
    help="Publish to the given region(s) instead of the default ones; can be specified multiple times")
args = ap.parse_args()

if 'AWS_PROFILE' not in os.environ and not 'AWS_DEFAULT_REGION' in os.environ:
    print(f"ERROR: You must set either the `AWS_PROFILE` or the `AWS_DEFAULT_REGION` environment variable")
    sys.exit(1)

tag = args.TAG
regex = re.compile(r"^\w+$")
if not regex.match(tag):
    print(f"ERROR: Invalid tag: '{tag}'; must be alphanumeric only")
    sys.exit(1)

package_version = "ACM-" + tag + "-" + datetime.datetime.utcnow().strftime("%Y%m%d-%H%M")

# Build Lambda packages

lambda_dir = "LambdaFunctions"
lambda_functions = [i for i in os.listdir(lambda_dir) if os.path.isdir(os.path.join(lambda_dir, i)) and i[0] != "."]

for i in lambda_functions:
    print(f"Building Lambda package for {i}")
    subprocess.check_call([f"./{lambda_dir}/package.sh", i])

# Modify the CloudFormation templates so that references to external resources
# (other CloudFormation templates, Lambda packages, etc.) point to the correct
# package version.

regex = re.compile(r"ACM-[0-9a-zA-Z]*-[0-9]{8}-[0-9]{4}")

def replace_package_version(filepath):
    tmpfilepath = filepath + ".tmp"
    with open(filepath) as input_file:
        with open(tmpfilepath, "w") as output_file:
            for line in input_file:
                line = regex.sub(package_version, line)
                output_file.write(line)
    os.rename(filepath, filepath + ".original")
    os.rename(tmpfilepath, filepath)
    os.unlink(filepath + ".original")

templates = [
    "CloudFormation/arkcase.yml",
    "CloudFormation/mariadb-user-secret.yml",
    "CloudFormation/amazonmq.yml",
    "CloudFormation/amqsecretcfg.yml",
]

for i in templates:
    replace_package_version(i)

# Push public files to public S3 buckets

default_regions = [
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

regions = args.region if args.region else default_regions
public_files = templates + [f"{lambda_dir}/{i}/{i}.zip" for i in lambda_functions]
s3 = boto3.client("s3")

for f in public_files:
    # Read file content
    data = open(f, "rb").read()

    for region in regions:
        bucket = "arkcase-public-" + region
        key = "DevOps/" + package_version + "/" + f
        print(f"Uploading file: {bucket}/{key}")
        s3.put_object(Bucket=bucket, Key=key, Body=data)

    if not args.keep_temporary:
        # Delete temporary files
        if f.endswith(".zip"):
            try:
                os.unlink(f)
            except Exception as e:
                print(f"Failed to delete temporary file '{f}': {str(e)}; ignored")

print(f"Files uploaded to: arkcase-public-REGION/DevOps/{package_version}/")
