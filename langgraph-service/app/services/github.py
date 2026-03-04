import os
from urllib import response
import requests

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
OWNER = os.getenv("GITHUB_REPO_OWNER")
REPO = os.getenv("GITHUB_REPO_NAME")


def create_pull_request(branch, title, body):

    url = f"https://api.github.com/repos/{OWNER}/{REPO}/pulls"

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }

    payload = {
        "title": title,
        "head": branch,
        "base": "main",
        "body": body
    }

    response = requests.post(url, headers=headers, json=payload)

    print("GitHub status:", response.status_code)
    print("GitHub response:", response.text)

    if response.status_code != 201:
       raise Exception(response.text)

    return response.json()

    