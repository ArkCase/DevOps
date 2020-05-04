#!/usr/bin/env python3

import os
import argparse
import datetime
import sys
import re
import boto3

# Preliminaries

this_path = os.path.abspath(__file__)
this_dir = os.path.dirname(this_path)
os.chdir(this_dir)

ap = argparse.ArgumentParser(description="Delete selected public files to ArkCase S3 public buckets")
ap.add_argument(
        "TAG",
        default="dev",
        help="Package tag to delete (dev, prod, staging, etc.)")
ap.add_argument(
        "-d",
        "--date",
        default=datetime.datetime.utcnow().strftime("%Y%m%d-%H%M"),
        help="Delete files before this date; format: YYYYMMDD-HHMM; default: delete everything for the given tag")
ap.add_argument(
        "-r",
        "--region",
        default=[],
        action="append",
        help="Publish to the given region(s) instead of the default ones; can be specified multiple times")
ap.add_argument(
        "-k",
        "--dry-run",
        default=False,
        action="store_true",
        help="Don't actually delete the files, just print out what would be done")
ap.add_argument(
        "-v",
        "--verbose",
        default=False,
        action="store_true",
        help="Print a lot of output")
args = ap.parse_args()

if 'AWS_PROFILE' not in os.environ and not 'AWS_DEFAULT_REGION' in os.environ:
    print(f"ERROR: You must set either the `AWS_PROFILE` or the `AWS_DEFAULT_REGION` environment variable")
    sys.exit(1)

tag = args.TAG
pattern = re.compile(r"^\w+$")
if not pattern.match(tag):
    print(f"ERROR: Invalid tag: '{tag}'; must be alphanumeric only")
    sys.exit(1)

# Scan public S3 buckets

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
s3 = boto3.client("s3")
pattern = re.compile(f"ACM-{tag}-" + r"(\d{8}-\d{4})")

def process_items(bucket, items):
    for item in items:
        key = item['Key']
        version = item['VersionId']
        result = re.findall(pattern, key)
        if not result:
            if args.verbose:
                print(f"File doesn't match, skipped: '{bucket}/{key}', version '{version}'")
            continue
        ts = result[0]
        if ts > args.date:
            if args.verbose:
                print(f"File too recent, skipped: '{bucket}/{key}', version '{version}'")
            continue
        if args.dry_run:
            print(f"Would delete: '{bucket}/{key}', version '{version}'")
        else:
            print(f"Deleting: '{bucket}/{key}', version '{version}'")
            s3.delete_object(
                    Bucket=bucket,
                    Key=key,
                    VersionId=version)


next_key_marker = None
next_version_id_marker = None
for region in regions:
    bucket = f"arkcase-public-{region}"
    if args.verbose:
        print(f"Scanning bucket '{bucket}'")
    finished = False
    while not finished:
        if next_key_marker:
            response = s3.list_object_versions(
                    Bucket=bucket,
                    MaxKeys=100,
                    Prefix="DevOps/",
                    KeyMarker=next_key_marker,
                    VersionIdMarker=next_version_id_marker)
        else:
            response = s3.list_object_versions(
                    Bucket=bucket,
                    MaxKeys=100,
                    Prefix="DevOps/")

        if 'IsTruncated' in response and response['IsTruncated']:
            next_key_marker = response['NextKeyMarker']
            next_version_id_marker = response['NextVersionIdMarker']
        else:
            finished = True

        if 'Versions' in response:
            process_items(bucket, response['Versions'])
        if 'DeleteMarkers' in response:
            process_items(bucket, response['DeleteMarkers'])
