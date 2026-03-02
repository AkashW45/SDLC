
import os
import json
# sdlc_service.py
import os
import json
from cerebras.cloud.sdk import Cerebras

client = Cerebras(api_key=os.getenv("CEREBRAS_API_KEY"))

def call_llm(system_prompt: str, user_prompt: str) -> dict:
    response = client.chat.completions.create(
        model="gpt-oss-120b",
        temperature=0,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )

    raw = response.choices[0].message.content

    return json.loads(raw)

def generate_blueprint(requirement: str) -> dict:

    return call_llm(
        system_prompt="""
You are a senior Business Analyst.
Generate a complete BRD.
Return ONLY valid JSON.
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
6. Every node MUST include "traced_to".
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