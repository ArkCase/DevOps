#!/usr/bin/env python3

import os
from flask import Flask, request, make_response
import requests
import json

backend_url = os.environ['BACKEND_URL']

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

@app.route("/")
def hello():
    if backend_url.endswith("/"):
        url = backend_url + "fromweb"
    else:
        url = backend_url + "/fromweb"

    headers = {}
    for header in tracing_headers:
        if header in request.headers:
            value = request.headers[header]
            headers[header] = value
            print(f"Propagating tracing header: {header}: {value}", flush=True)

    try:
        print(f"Querying backend: {url}", flush=True)
        response = requests.get(url, headers=headers)
        print(f"Backend returned status: {response.status_code}", flush=True)
        if response.status_code != 200:
            raise RuntimeError(f"Backend error")
        print(f"Backend returned message: {response.text}", flush=True)
        status_code = 200
        j = json.loads(response.text)
        msg = j['message']
        ts = j['timestamp_utc']
        data = {
            'backend': msg,
            'timestamp_utc': ts
        }

    except Exception as e:
        status_code = 503
        data = {'reason': str(e)}

    data['status_code'] = status_code
    return make_response(json.dumps(data), status_code)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
