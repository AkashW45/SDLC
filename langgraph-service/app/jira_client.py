import os
import base64
import httpx


def fetch_jira_metadata(project_key: str) -> dict:
    """
    Fetch Jira project metadata and normalize into deterministic structure.
    """

    email = os.getenv("JIRA_EMAIL")
    token = os.getenv("JIRA_API_TOKEN")
    domain = os.getenv("JIRA_BASE_URL")

    if not all([email, token, domain]):
        raise ValueError("JIRA environment variables not configured")

    credentials = base64.b64encode(
        f"{email}:{token}".encode()
    ).decode()

    headers = {
        "Authorization": f"Basic {credentials}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    # Fetch createmeta
    url = (
        f"https://{domain}/rest/api/3/issue/createmeta"
        f"?projectKeys={project_key}"
        f"&expand=projects.issuetypes.fields"
    )

    response = httpx.get(url, headers=headers, timeout=15)

    if response.status_code != 200:
        raise Exception(f"Failed to fetch Jira metadata: {response.text}")

    data = response.json()

    if not data.get("projects"):
        raise Exception("Project not found in Jira metadata")

    project = data["projects"][0]

    # Normalize issue types into dict by name
    issue_types = {}
    for it in project.get("issuetypes", []):
        issue_types[it["name"]] = it["id"]

    # Fetch priorities separately
    priorities_url = f"https://{domain}/rest/api/3/priority"
    priorities_response = httpx.get(priorities_url, headers=headers, timeout=15)

    if priorities_response.status_code != 200:
        raise Exception("Failed to fetch Jira priorities")

    priorities = {}
    for p in priorities_response.json():
        priorities[p["name"]] = p["id"]

    return {
        "project_id": project["id"],
        "issue_types": issue_types,
        "priorities": priorities
    }