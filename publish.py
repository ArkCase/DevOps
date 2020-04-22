#!/usr/bin/env python3

import argparse
import sys
import datetime
import os
import subprocess
import boto3
import hashlib
import binascii

# Preliminaries

this_path = os.path.abspath(__file__)
this_dir = os.path.dirname(this_path)
os.chdir(this_dir)

ap = argparse.ArgumentParser(description="Push public files to ArkCase S3 public buckets")
ap.add_argument("-m", "--skip-mariadb-rotation-lambda",
    default=False, action="store_true",
    help="Skip the MariaDB Rotation Lambda function package")
ap.add_argument("-w", "--skip-maintenance-windows-lambda",
    default=False, action="store_true",
    help="Skip the Maintenance Windows Lambda function package")
ap.add_argument("-k", "--keep-temporary",
    default=False, action="store_true",
    help="Don't delete temporary and intermediate files")
args = ap.parse_args()

if 'AWS_PROFILE' not in os.environ and not 'AWS_DEFAULT_REGION' in os.environ:
    print(f"ERROR: You must set either the `AWS_PROFILE` or the `AWS_DEFAULT_REGION` environment variable")
    sys.exit(1)

package_version = datetime.datetime.now().strftime("%Y%m%d-%H%M")

# Build packages as necessary

if not args.skip_mariadb_rotation_lambda:
    print(f"Building MariaDB rotation Lambda function package")
    subprocess.check_call(["./mariadb_rotation_lambda/package.sh"])

if not args.skip_maintenance_windows_lambda:
    print(f"Building Maintenance Windows Lambda function package")
    subprocess.check_call(["./maintenance_windows_lambda/package.sh"])

# Modify the CloudFormation templates so that pointers to external resources
# (other CloudFormation templates, Lambda packages, etc.) point to the correct
# package version.

processed_extension = ".processed"

def replace_package_version(filepath):
    newfilepath = filepath + processed_extension
    with open(filepath) as input_file:
        with open(newfilepath, "w") as output_file:
            for line in input_file:
                line = line.replace("PACKAGE_VERSION", package_version)
                output_file.write(line)
    return newfilepath

templates = [
    "CloudFormation/arkcase.yml",
    "CloudFormation/mariadb.yml"
]

processed_templates = [replace_package_version(i) for i in templates]

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

public_files = processed_templates

if not args.skip_mariadb_rotation_lambda:
    public_files.append("mariadb_rotation_lambda/mariadb_rotation_lambda.zip")

if not args.skip_maintenance_windows_lambda:
    public_files.append("maintenance_windows_lambda/maintenance_windows_lambda.zip")

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
        if f.endswith(processed_extension):
            # Strip ".processed" extension when uploading
            n = len(processed_extension)
            key = "DevOps/" + package_version + "/" + f[:-n]
        else:
            key = "DevOps/" + package_version + "/" + f

        try:
            response = s3.head_object(Bucket=bucket, Key=key)
            # NB: The ETag is the MD5 checksum, except when the file has been
            #     uploaded in multi-parts, which we don't do in this script.
            #     Worst case scenario is that the file gets uploaded again,
            #     anyway... Also, strangely, the ETag comes surrounded by
            #     double quotes, so we have to get rid of those first.
            sum2 = response['ETag'].strip('"')
        except Exception as e:
            sum2 = ""

        # Upload file only if it had changed
        # NB: If we upload the file every time, S3 will create a new version,
        #     even if the file is exactly the same, and we will be billed for
        #     storing identical versions.
        if sum1 == sum2:
            print(f"Same MD5 checksum, not uploading: {bucket}/{key}")
        else:
            print(f"Uploading file: {bucket}/{key}")
            s3.put_object(Bucket=bucket, Key=key, Body=data)

    if not args.keep_temporary:
        # Delete temporary files
        if f.endswith(".zip") or f.endswith(processed_extension):
            try:
                os.unlink(f)
            except Exception as e:
                print(f"Failed to delete temporary file [{f}]: {str(e)}; ignored")

print(f"Files uploaded to: arkcase-public-REGION/DevOps/{package_version}/")
