#!/usr/bin/env python3

import os
from flask import Flask
import json

msg = os.environ.get('TEST_BACKEND_MESSAGE', "Bugs Bunny was here")

app = Flask(__name__)


@app.route("/", defaults={'path': ""})
@app.route("/<path:path>")
def main_route(path):
    data = {
        'message': f"Message from test-backend: {msg}"
    }
    return json.dumps(data)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
