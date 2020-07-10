#!/usr/bin/env python3

import os
from flask import Flask
import requests
import json

backend_url = os.environ['BACKEND_URL']

app = Flask(__name__)

@app.route("/")
def hello():
    try:
        if backend_url.endswith("/"):
            url = backend_url + "fromweb"
        else:
            url = backend_url + "/fromweb"
        print(f"Querying backend: {url}", flush=True)
        response = requests.get(url)
        print(f"Backend returned status: {response.status_code}", flush=True)
        if response.status_code != 200:
            raise RuntimeError(f"Gateway error")
        print(f"Backend returned message: {response.text}", flush=True)
        data = json.loads(response.text)['message']
    except Exception as e:
        data = f"Backend unavailable: {str(e)}"
    return f"<html><body>Backend returned: {data}</body></html>\n"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081)
