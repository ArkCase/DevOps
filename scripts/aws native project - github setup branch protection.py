#!/usr/bin/env python

# this script sets up branch protection on the develop branch in all of the repos in the list defined.
# This script expects a personal access token to be provided via the environment variable personal_access_token
# an example for setting this personal_access_token is provided in setenv.sh which can be sourced in your current terminal by running:
#       . ./setenv.sh
#

import requests
from os import environ

personal_access_token = environ['personal_access_token']
owner = 'ArkCase'
branch = 'develop'
repos = ['ark_base',
         'ark_base_java11_tomcat9',
         'ark_base_java8_tomcat9',
         'ark_base_java8',
         'ark_base_java11',
         'ark_snowbound',
         'ark_activemq',
         'ark_solr',
         'ark_cloudconfig',
         'ark_solr_exporter',
         'ark_samba',
         'ark_postfix',
         'ark_iac_aws',
         'ark_pentaho',
         'ark_alfresco',
         'ark_pentaho_ee',
         'ark_prometheus',
         'ark_prometheus_nodeexp',
         'ark_prometheus_alertman',
         'ark_prometheus_pushgate',
         'ark_google_cadvisor',
         'ark_grafana_reporter',
         'ark_grafana_imagerend',
         'ark_grafana',
         ]

for repo in repos:
    r = requests.put(
        f'https://api.github.com/repos/{owner}/{repo}/branches/{branch}/protection',
        headers={
            'Accept': 'application/vnd.github.luke-cage-preview+json',
            'Authorization': 'Token {0}'.format(personal_access_token)
        },

        json={
            "enforce_admins": True,
            "required_status_checks": None,
            "required_pull_request_reviews": {
                "dismiss_stale_reviews": True,
                "require_code_owner_reviews": True,
                "required_approving_review_count": 2
            },
            "restrictions": {
                "users": [
                    "JonHolman",
                    "fabricetriboix",
                    "david-oc-miller",
                    "ymuwakki",
                    "naveen-armedia",
                    "dheeraj-armedia",
                    "drivera-armedia",
                ],
                "teams": []
            },
            "required_conversation_resolution": True,
        }
    )

    print(repo, r.status_code, f'https://github.com/ArkCase/{repo}/')
