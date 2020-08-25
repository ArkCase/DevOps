#!/usr/bin/env python3

import requests
from flask import Flask, request
import os
import json

response = requests.get("http://169.254.169.254/latest/meta-data/local-hostname")
hostname = response.content.decode('utf-8')

app = Flask(__name__)

users_file = "/app/data/users.json"


def get_users():
    users = []
    if os.path.exists(users_file):
        with open(users_file) as f:
            data = f.read()
            users = json.loads(data)
    return users


def save_users(users):
    data = json.dumps(users, indent=2)
    with open(users_file, "w") as f:
        f.write(data)
        f.write("\n")


def add_user(username):
    users = []
    if os.path.exists(users_file):
        with open(users_file) as f:
            data = f.read()
            users = json.loads(data)
    user = {
        'username': username
    }
    users.append(user)
    save_users(users)


def delete_user(username):
    users = get_users()
    for i in range(len(users)):
        if users[i]['username'] == username:
            del users[i]
            break
    save_users(users)


@app.route("/", defaults={'path': ""})
@app.route("/<path:path>")
def main_route(path):
    data = {
        'message': f"Running from: {hostname}"
    }
    return json.dumps(data)


@app.route("/users", methods=["GET"])
def users_get():
    data = {
        'users': get_users()
    }
    return json.dumps(data)


@app.route("/user", methods=["PUT"])
def users_put():
    body = request.get_data()
    if type(body) == bytes:
        body = body.decode('utf-8')
    data = json.loads(body)
    add_user(data['username'])
    return "OK"


@app.route("/user", methods=["DELETE"])
def users_delete():
    body = request.get_data()
    if type(body) == bytes:
        body = body.decode('utf-8')
    data = json.loads(body)
    delete_user(data['username'])
    return "OK"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
