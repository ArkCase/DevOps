#!/usr/bin/env python3

import uuid
import json
import requests


def handler(event, context):
    """
    Handle an operation for a "MaintenanceWindows" CloudFormation custom
    resource.

    The event received has the following pattern:

    {
        "RequestType": "Create",
        "ResponseURL": "https://pre-signed-s3-url-for-response",
        "StackId": "arn:aws:cloudformation:us-west-2:123456789012:stack/stack-name/guid",
        "RequestId": "unique id for this request",
        "ResourceType": "Custom::MaintenanceWindows",  # or whatever
        "LogicalResourceId": "MaintenanceWindows",     # or whatever
        "ResourceProperties": {
          "Start": "Sun:08:00"  # Maintenance window start time in UTC
        }
    }

    """
    if event['RequestType'] == "Delete":
        print(f"Request type is 'Delete': nothing to do")
        send_response(event, True)
        return
    print(f"Request type is '{event['RequestType']}'")

    try:
        data = compute_maintenance_windows(event)
    except Exception as e:
        print(f"ERROR: {str(e)}")
        send_response(event, False, str(e))
        return
    print(f"Success: {data}")
    send_response(event, True, "Success", data)


def compute_maintenance_windows(event):
    # Extract start specification
    start = event['ResourceProperties']['Start']
    start_day = start[0:3].lower()
    start_hour = int(start[4:6])
    start_min = int(start[7:9])

    # 5' window to block incoming traffic to ArkCase
    start = Timestamp(start_day, start_hour, start_min)
    data = {}
    data['StartBlockTraffic'] = start.get_day_and_time()  # TODO: cron?
    end = start.next(5)

    # 30' window to perform backups on all RDS instances
    start = end
    data['StartRdsBackup'] = start.get_time()
    end = start.next(30)
    data['EndRdsBackup'] = end.get_time()

    # 30' window to perform Alfresco RDS maintenance
    start = end
    data['StartAlfrescoRdsMaintenance'] = start.get_day_and_time()
    end = start.next(30)
    data['EndAlfrescoRdsMaintenance'] = end.get_day_and_time()

    # 30' window to perform AmazonMQ maintenance
    start = end
    data['StartAmazonmqMaintenanceDayOfWeek'] = start.get_day_name()
    data['StartAmazonmqMaintenanceTimeOfDay'] = start.get_time()
    end = start.next(30)

    # End of maintenance
    data['EndBlockTraffic'] = end.get_day_and_time()  # TODO: cron?

    return data


days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
full_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class Timestamp:
    def __init__(self, day, hour, min):
        day = day.lower()
        if day not in days:
            raise ValueError(f"Invalid day: {day}")
        self.day = days.index(day)
        self.hour = int(hour)
        if self.hour < 0 or self.hour >= 24:
            raise ValueError(f"Invalid start hour: {hour}")
        self.min = int(min)
        if self.min < 0 or self.min >= 60:
            raise ValueError(f"Invalid start minutes: {min}")

    def next(self, duration_min):
        if duration_min <= 0:
            raise ValueError(f"Invalid time duration: {duration_min}")

        next_min = self.min + duration_min
        carry = 0
        while next_min >= 60:
            next_min -= 60
            carry += 1

        next_hour = self.hour + carry
        carry = 0
        while next_hour >= 24:
            next_hour -= 24
            carry += 1

        next_day = (self.day + carry) % 7
        return Timestamp(days[next_day], next_hour, next_min)

    def get_time(self):
        return f"{self.hour:02d}:{self.min:02d}"

    def get_day_and_time(self):
        tmp = days[self.day].title()
        return f"{tmp}:{self.hour:02d}:{self.min:02d}"

    def get_day_name(self):
        return full_days[self.day]


def send_response(event, success: bool, msg="", data={}):
    response = {
        'Status': "SUCCESS" if success else "FAILED",
        'Reason': msg,
        'PhysicalResourceId': str(uuid.uuid4()),
        'StackId': event['StackId'],
        'RequestId': event['RequestId'],
        'LogicalResourceId': event['LogicalResourceId'],
        'Data': data
    }
    headers = {
        'Content-Type': ""
    }
    body = json.dumps(response)
    requests.put(event['ResponseURL'], headers=headers, data=body)
