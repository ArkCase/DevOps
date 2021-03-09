#!/usr/bin/env python3

import os
from flask import Flask, request, make_response
import json
import random
import time
import datetime

app = Flask(__name__)

@app.route("/", defaults={'path': ""})
@app.route("/<path:path>")
def hello(path):
    time.sleep(random.random() / 2.0)  # Simulate some work
    data = {
        'now_utc': datetime.datetime.utcnow().isoformat(),
        'status_code': 200
    }
    return make_response(json.dumps(data), 200)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8082)
