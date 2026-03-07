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

    if response.status_code == 201:
       return response.json()

# PR already exists
    if response.status_code == 422 and "already exists" in response.text:
       print("PR already exists. Fetching existing PR...")

       pr_list_url = f"https://api.github.com/repos/{OWNER}/{REPO}/pulls?head={OWNER}:{branch}&state=open"
       pr_resp = requests.get(pr_list_url, headers=headers)

       return pr_resp.json()[0]

    raise Exception(response.text)

def get_pr_files(pr_number):

    url = f"https://api.github.com/repos/{OWNER}/{REPO}/pulls/{pr_number}/files"

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }

    response = requests.get(url, headers=headers)

    print("GitHub PR files status:", response.status_code)

    if response.status_code != 200:
        raise Exception(response.text)

    return response.json()  

def extract_diff_summary(files):

    summary = []

    for f in files:
        if "patch" in f and f["patch"]:
            summary.append({
                "file": f["filename"],
                "patch": f["patch"]
            })

    return summary

    