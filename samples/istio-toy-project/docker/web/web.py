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
        headers[header] = request.headers.get(header)
        if headers[header]:
            print(f"Header: {header}: {headers[header]}", flush=True)

    try:
        print(f"Querying backend: {url}", flush=True)
        response = requests.get(url, headers=headers)
        print(f"Backend returned status: {response.status_code}", flush=True)
        if response.status_code != 200:
            raise RuntimeError(f"Gateway error")
        print(f"Backend returned message: {response.text}", flush=True)
        status_code = 200
        msg = json.loads(response.text)['message']
        data = {'backend': msg}

    except Exception as e:
        status_code = 503
        data = {'reason': str(e)}

    data['status_code'] = status_code
    return make_response(json.dumps(data), status_code)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081)
