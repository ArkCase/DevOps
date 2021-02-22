#!/usr/bin/env python3

import os
from flask import Flask, request, make_response
import json
import random
import time

hostname = os.environ['HOSTNAME']

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
    time.sleep(random.random())  # Simulate some work
    data = {
        'message': f"I am backend {hostname}"
    }

    status_code = 200
    if 'SIMULATE_ERROR_RATE' in os.environ:
        rate = float(os.environ['SIMULATE_ERROR_RATE'])
        if random.random() < rate:
            print(f"Simulating 500 error", flush=True)
            status_code = 500
            data = {
                'reason': 'Backend internal failure'
            }

    return make_response(json.dumps(data), status_code)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
