#!/usr/bin/env python3

import os
from flask import Flask, request, make_response
import requests
import json
import random
import time

hostname = os.environ['HOSTNAME']
timeserver_url = os.environ['TIMESERVER_URL']
if 'SIMULATE_ERROR_RATE' in os.environ:
    error_rate = float(os.environ['SIMULATE_ERROR_RATE'])
    print(f"SIMULATE_ERROR_RATE: {error_rate}", flush=True)
else:
    error_rate = None

tracing_headers = [
        "x-request-id",
        "x-b3-traceid",
        "x-b3-spanid",
        "x-b3-parentspanid",
        "x-b3-sampled",
        "x-b3-flags",
        "x-ot-span-context",
        "x-cloud-trace-context",
        "traceparent",
        "grpc-trace-bin"
]

app = Flask(__name__)

@app.route("/", defaults={'path': ""})
@app.route("/<path:path>")
def hello(path):
    time.sleep(random.random() / 2.0)  # Simulate some work

    data = {
        'message': f"I am backend {hostname}"
    }

    if error_rate and random.random() < error_rate:
        print(f"Simulating 500 error", flush=True)
        status_code = 500
        data['reason'] = 'Backend internal failure'

    else:
        # Query time server
        headers = {}
        for header in tracing_headers:
            if header in request.headers:
                value = request.headers[header]
                headers[header] = value
                print(f"Propagating tracing header: {header}: {value}", flush=True)

        print(f"Querying timeserver: {timeserver_url}", flush=True)
        response = requests.get(timeserver_url, headers=headers)
        print(f"Timeserver returned status: {response.status_code}", flush=True)
        if response.status_code != 200:
            raise RuntimeError(f"Timeserver error")
        print(f"Timeserver returned message: {response.text}", flush=True)
        ts = json.loads(response.text)['now_utc']
        data['timestamp_utc'] = ts
        status_code = 200

        time.sleep(random.random() / 2.0)  # Simulate more work

    data['status_code'] = status_code
    return make_response(json.dumps(data), status_code)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081)
