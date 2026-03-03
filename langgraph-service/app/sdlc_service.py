
import os
import json
# sdlc_service.py

from .sprint_planner import generate_sprint_plan

import requests


from groq import Groq


client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def call_llm(system_prompt: str, user_prompt: str) -> dict:

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        temperature=0,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )

    raw = response.choices[0].message.content.strip()

    # Remove markdown fences if model adds them
    if raw.startswith("```"):
        raw = raw.split("```")[1]

    return json.loads(raw)

def generate_blueprint(requirement: str) -> dict:

    return call_llm(
        system_prompt="""
You are a senior Business Analyst.
Generate a complete BRD.
Return ONLY valid JSON.
Return ONLY valid JSON.
Do not include explanations.
Do not include markdown.
""",
        user_prompt=f"""
Generate a BRD for the following requirement:

{requirement}
"""
    )

def generate_prd_from_blueprint(blueprint: dict) -> dict:

    return call_llm(
        system_prompt="""
You are a Product Owner.
Generate a detailed PRD from the given BRD.
Return ONLY valid JSON.
Return ONLY valid JSON.
Do not include explanations.
Do not include markdown.
""",
        user_prompt=json.dumps(blueprint)
    )

def generate_architecture_from_prd(canonical: dict) -> dict:
    """
    LLM receives only canonical facts.
    Cannot invent beyond them.
    """

    system_prompt = """
You are a strict software architect.

Rules:
1. Every node MUST be justified by a functional or non-functional requirement.
2. Do NOT invent technologies.
3. If requirements are simple, architecture must remain simple.
4. 5-8 nodes maximum.
5. Return ONLY JSON.
6.Return ONLY valid JSON.
7.Do not include explanations.
8.Do not include markdown.
9. Every node MUST include "traced_to".
"""

    user_prompt = f"""
Project: {canonical['project_name']}

Functional Requirements:
{json.dumps(canonical['functional_requirements'], indent=2)}

Non Functional Requirements:
{json.dumps(canonical['non_functional_requirements'], indent=2)}

Actors:
{json.dumps(canonical['actors'], indent=2)}

Generate architecture JSON with:

{{
  "nodes": [
    {{
      "id": "UPPERCASE_ID",
      "name": "Human Name",
      "type": "service|database|external",
      "zone": "external|core|observability",
      "traced_to": "exact requirement text"
    }}
  ],
  "edges": [
    {{
      "source": "ID",
      "target": "ID",
      "protocol": "REST|SQL|internal"
    }}
  ]
}}
"""

    result = call_llm(system_prompt, user_prompt)

    # Deterministic validation
    valid_nodes = []
    for node in result.get("nodes", []):
        if node.get("traced_to") in canonical["functional_requirements"] \
           or node.get("traced_to") in canonical["non_functional_requirements"]:
            valid_nodes.append(node)

    result["nodes"] = valid_nodes

    return result


def canonicalize_prd(prd: dict, brd: dict) -> dict:
    """
    Converts any PRD/BRD shape into canonical deterministic schema.
    No LLM here. Pure logic.
    """

    def get(obj, *keys):
        for k in keys:
            if obj.get(k):
                return obj[k]
        return None

    # Project name
    project_name = (
        get(prd, "title", "projectTitle") or
        get(brd, "project_name", "projectTitle") or
        "SYSTEM"
    )

    # Functional Requirements
    raw_fr = (
        get(prd, "functional_requirements", "functionalRequirements") or
        get(brd, "functional_requirements", "functionalRequirements") or
        []
    )

    functional_requirements = []
    for fr in raw_fr:
        if isinstance(fr, str):
            functional_requirements.append(fr)
        elif isinstance(fr, dict):
            functional_requirements.append(
                fr.get("description") or fr.get("title") or ""
            )

    # Non-functional
    raw_nfr = (
        get(prd, "non_functional_requirements", "nonFunctionalRequirements") or
        []
    )

    non_functional_requirements = []
    for nfr in raw_nfr:
        if isinstance(nfr, str):
            non_functional_requirements.append(nfr)
        elif isinstance(nfr, dict):
            non_functional_requirements.append(
                nfr.get("description") or ""
            )

    # Actors
    raw_personas = (
        get(prd, "user_personas", "userPersonas") or
        get(brd, "stakeholders") or
        []
    )

    actors = []
    for p in raw_personas:
        if isinstance(p, str):
            actors.append(p)
        elif isinstance(p, dict):
            actors.append(p.get("role") or p.get("name") or "")

    return {
        "project_name": project_name,
        "functional_requirements": functional_requirements[:10],
        "non_functional_requirements": non_functional_requirements[:5],
        "actors": [a for a in actors if a][:5]
    }

import uuid

import uuid

def deterministic_architecture_plan(architecture: dict) -> dict:
    epics = []

    for node in architecture.get("nodes", []):
        node_id = node["id"]
        node_name = node["name"]
        node_type = node["type"]

        epic_id = f"E-{uuid.uuid4().hex[:6].upper()}"

        epic = {
            "epic_id": epic_id,
            "title": f"{node_name} Implementation",
            "derived_from_node": node_id,
            "tickets": []
        }

        if node_type == "service":
            epic["tickets"].append({
                "ticket_id": f"BE-{uuid.uuid4().hex[:5].upper()}",
                "type": "Story",
                "component": node_id,
                "description": f"Implement business logic for {node_name}",
                "layer": "backend",
                "independent": True,
                "depends_on": []
            })

            epic["tickets"].append({
                "ticket_id": f"BE-{uuid.uuid4().hex[:5].upper()}",
                "type": "Task",
                "component": node_id,
                "description": f"Expose REST API endpoints for {node_name}",
                "layer": "backend",
                "independent": True,
                "depends_on": []
            })

        if node_type == "external":
            epic["tickets"].append({
                "ticket_id": f"FE-{uuid.uuid4().hex[:5].upper()}",
                "type": "Story",
                "component": node_id,
                "description": f"Build UI component for {node_name}",
                "layer": "frontend",
                "independent": True,
                "depends_on": []
            })

        if node_type == "database":
            epic["tickets"].append({
                "ticket_id": f"DB-{uuid.uuid4().hex[:5].upper()}",
                "type": "Task",
                "component": node_id,
                "description": f"Design schema and migrations for {node_name}",
                "layer": "backend",
                "independent": True,
                "depends_on": []
            })

        epics.append(epic)

    return {"epics": epics}




def build_sprint_plan(canonical: dict, architecture: dict, jira_meta: dict) -> dict:
    """
    Returns Jira-ready tickets using metadata-driven mapping.
    """
    

    project_id = jira_meta["project_id"]
    issue_types = jira_meta["issue_types"]  # dict by name
    priorities = jira_meta["priorities"]    # dict by name

    flat_tickets = []

    # 1️⃣ LLM Product Planning
    try:
        prd_text = "\n".join(canonical.get("functional_requirements", []))
        llm_plan = generate_sprint_plan(prd_text)

        if hasattr(llm_plan, "model_dump"):
            llm_plan = llm_plan.model_dump()

        for epic in llm_plan.get("epics", []):

            flat_tickets.append({
                "fields": {
                    "project": {"id": project_id},
                    "summary": epic["title"],
                    "description": epic["description"],
                    "issuetype": {"id": issue_types["Epic"]},
                    "priority": {"id": priorities["Medium"]},
                    "labels": ["product"]
                }
            })

            for story in epic.get("stories", []):
                flat_tickets.append({
                    "fields": {
                        "project": {"id": project_id},
                        "summary": story["title"],
                        "description": story["description"],
                        "issuetype": {"id": issue_types["Story"]},
                        "priority": {"id": priorities["Medium"]},
                        "labels": ["product"],
                        "custom_story_points": story.get("story_points")
                    }
                })

    except Exception as e:
        print("LLM planning failed:", e)

    # 2️⃣ Deterministic Architecture Tickets
    infra_plan = deterministic_architecture_plan(architecture)

    for epic in infra_plan.get("epics", []):

        flat_tickets.append({
            "fields": {
                "project": {"id": project_id},
                "summary": epic["title"],
                "description": f"Derived from architecture node {epic['derived_from_node']}",
                "issuetype": {"id": issue_types["Epic"]},
                "priority": {"id": priorities["High"]},
                "labels": ["architecture"]
            }
        })

        for ticket in epic.get("tickets", []):
            flat_tickets.append({
                "fields": {
                    "project": {"id": project_id},
                    "summary": ticket["description"],
                    "description": ticket["description"],
                    "issuetype": {"id": issue_types[ticket["type"]]},
                    "priority": {"id": priorities["High"]},
                    "labels": [ticket["layer"]]
                }
            })

    return {
        "project": project_id,
        "sprint_duration": "2 weeks",
        "tickets": flat_tickets
    }