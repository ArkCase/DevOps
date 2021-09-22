#!/usr/bin/env python3

import requests
import re
from natsort import natsorted


tomcat_major = 9
github_user = "ArkCase"


def get_latest_tomcat_version():
    r = requests.get("https://archive.apache.org/dist/tomcat/tomcat-9/")
    assert(r.status_code == 200)
    tmp = set(re.findall(f'href="v{tomcat_major}.[0-9]+.[0-9]+', r.text))
    if not tmp:
        return None
    versions = [i[7:] for i in tmp]
    versions = natsorted(versions)
    print(versions)
    return versions[-1]


def get_arkcase_repos():
    """
    get_arkcase_repos() finds all the public repositories on GitHub belonging
    to the ArkCase user that have a `Dockerfile` at the root of the repo.
    """
    r = requests.get(f"https://api.github.com/users/{github_user}/repos")
    assert(r.status_code == 200)
    data = r.json()
    repos = {}
    for repo in data:
        repo_name = repo['name']
        branch = repo['default_branch']
        print(f"XXX checking repo {repo_name}, branch {branch}")
        r = requests.get(f"https://raw.githubusercontent.com/{github_user}/{repo_name}/{branch}/Dockerfile")
        if r.status_code == 200:
            print(f"XXX repo {repo_name} is good")
            repos[repo_name] = {'branch': branch}
    return repos


#latest_tomcat_version = get_latest_tomcat_version()
#print(f"Detected latest Tomcat version: {latest_tomcat_version}")

repos = get_arkcase_repos()
print(repos)
