

# sdlc_service.py

from app.api.sprint_planner import generate_sprint_plan

import requests
import time
import re
import json



import os
import json
import re
from groq import Groq

client = Groq(api_key=os.getenv("GROQ_API_KEY"))


class LLMOutputError(Exception):
    pass




def call_llm(system_prompt: str, user_prompt: str, retries: int = 5) -> dict:
    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=4096,
            )
            content = response.choices[0].message.content.strip()
            
            # Strip markdown fences if LLM wraps in ```json ... ```
            if content.startswith("```"):
                content = re.sub(r"```(?:json)?", "", content).strip().strip("```").strip()
            
            # Always return parsed dict, never raw string
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                # LLM returned non-JSON text, return as-is for non-JSON callers
                return content

        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "rate_limit" in error_str.lower():
                wait_time = 3 * (attempt + 1)
                print(f"[Rate limit hit] Waiting {wait_time}s before retry {attempt+1}/{retries}")
                time.sleep(wait_time)
            else:
                raise
    raise Exception("Max retries exceeded due to rate limiting")
    

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
Generate a PRD from the given BRD.

Rules:
1. Return ONLY valid JSON. No markdown, no explanations.
2. Be concise — every field must serve downstream sprint planning.
3. Required fields: projectTitle, productVision, functionalRequirements, nonFunctionalRequirements, stakeholders, scope.
4. functionalRequirements must be an array of objects with: id, title, description, priority, acceptanceCriteria (array of strings).
5. nonFunctionalRequirements must be an array of objects with: id, title, description, priority.
6. Do NOT include: useCases, uiComponents, dataModel, releasePlan, metricsAndSuccessCriteria, appendix, deliveryMilestones.
7. acceptanceCriteria per requirement: max 3 bullet points, concise.
8. Total response must stay under 3000 tokens.
""",
        user_prompt=json.dumps(blueprint)
    )

def generate_architecture_from_prd(canonical: dict) -> dict:
    canonical['project_name'] = canonical.get('project_name') or 'SYSTEM'
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

def extract_text_fields(obj):
    texts = []

    if isinstance(obj, str):
        cleaned = obj.strip()
        if len(cleaned) > 3:
            texts.append(cleaned)

    elif isinstance(obj, list):
        for item in obj:
            texts.extend(extract_text_fields(item))

    elif isinstance(obj, dict):
        for key, value in obj.items():

            # ignore metadata
            if key.lower() in {"id", "uuid", "priority", "version"}:
                continue

            texts.extend(extract_text_fields(value))

    return texts


def normalize_requirement_dynamic(r):
    texts = extract_text_fields(r)

    texts = list(dict.fromkeys(t for t in texts if len(t) > 3))

    if not texts:
        return ""

    return " ".join(texts)

def canonicalize_prd(prd: dict, brd: dict) -> dict:
    print(f"RAW_PRD_KEYS: {list(prd.keys())}")
    print(f"RAW_PRD_SAMPLE: {json.dumps(prd, indent=2)[:500]}")

    def get(obj, *keys):
        if not isinstance(obj, dict):
            return None
        lower_map = {k.lower(): v for k, v in obj.items()}
        for k in keys:
            val = lower_map.get(k.lower())
            if val:
                return val
        return None

    project_name = (
        get(prd, "title", "projectTitle", "DocumentTitle", "Project", "ProjectName") or
        get(brd, "project_name", "projectTitle") or
        "SYSTEM"
    )

    raw_fr = (
        get(prd, "functional_requirements", "functionalRequirements",
            "FunctionalRequirements", "features", "Features") or
        get(brd, "functional_requirements", "functionalRequirements") or
        []
    )

    raw_nfr = (
        get(prd, "non_functional_requirements", "nonFunctionalRequirements",
            "NonFunctionalRequirements", "nfr") or
        []
    )

    raw_personas = (
        get(prd, "user_personas", "userPersonas", "UserPersonas",
            "stakeholders", "Stakeholders", "users") or
        get(brd, "stakeholders") or
        []
    )

    # 🔥 NORMALIZE FUNCTIONAL REQUIREMENTS
    normalized_fr = []

    

    for r in raw_fr:
        normalized = normalize_requirement_dynamic(r)
        if normalized:
           normalized_fr.append(normalized)

    # 🔥 NORMALIZE NFR
    normalized_nfr = []

    for r in raw_nfr:
        if isinstance(r, dict):
            desc = r.get("description") or r.get("text") or ""
            normalized_nfr.append(desc)
        else:
            normalized_nfr.append(str(r))
    
    normalized_fr = [r for r in normalized_fr if r.strip()]
    canonical = {
        "project_name": project_name,
        "functional_requirements": normalized_fr,
        "non_functional_requirements": normalized_nfr,
        "actors": raw_personas
    }
    

    return canonical
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





def to_adf(text: str) -> dict:
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {
                        "type": "text",
                        "text": text or ""
                    }
                ]
            }
        ],
    }


def wrap_tickets_with_adf(sprint_plan: dict) -> dict:
    for ticket in sprint_plan.get("tickets", []):
        fields = ticket.get("fields", {})
        raw_desc = fields.get("description")

        # If already valid ADF, leave it
        if isinstance(raw_desc, dict) and raw_desc.get("type") == "doc":
            continue

        # Convert string or None to ADF
        fields["description"] = to_adf(str(raw_desc or ""))

    return sprint_plan

def build_sprint_plan(
    canonical: dict,
    architecture: dict,
    jira_meta: dict,
    project_key: str
) -> dict:
    """
    Returns Jira-ready tickets using metadata-driven mapping.
    """
    
    issue_types = jira_meta["issue_types"]  # dict by name
    priorities = jira_meta["priorities"]    # dict by name
    story_points_field = jira_meta.get("dynamic_fields", {}).get("story_points")

    flat_tickets = []

    # 1️⃣ LLM Product Planning
    try:
        prd_text = "\n".join(
    r if isinstance(r, str) else json.dumps(r)
    for r in canonical.get("functional_requirements", [])
)
        print(f"PRD_TEXT_DEBUG: '{prd_text[:300]}'")  # ← ADD THIS
        print(f"CANONICAL_KEYS: {list(canonical.keys())}")  # ← ADD THIS TOO
        print(f"CANONICAL_FR: {canonical.get('functional_requirements', [])}")
        llm_plan = generate_sprint_plan(prd_text)

        if hasattr(llm_plan, "model_dump"):
            llm_plan = llm_plan.model_dump()

        for epic in llm_plan.get("epics", []):

            flat_tickets.append({
                "fields": {
                    "project": {"key": project_key},
                    "summary": epic["title"],
                    "description": epic["description"],
                    "issuetype": {"id": issue_types["Epic"]},
                    "priority": {"id": priorities["Medium"]},
                    
                    "labels": ["product"]
                }
            })

        for story in epic.get("stories", []):
    # Format acceptance criteria into description
            ac_list = story.get("acceptance_criteria", [])
            ac_text = ""
            if ac_list:
               ac_text = "\n\nAcceptance Criteria:\n" + "\n".join(f"- {ac}" for ac in ac_list)
    
            full_description = story["description"] + ac_text
    
            fields = {
        "project": {"key": project_key},
        "summary": story["title"],
        "description": full_description,  # AC embedded in description
        "issuetype": {"id": issue_types["Story"]},
        "priority": {"id": priorities["Medium"]},
        "labels": ["product"]
    }
    
            if story_points_field and story.get("story_points") is not None:
               fields[story_points_field] = story.get("story_points")
    
            flat_tickets.append({"fields": fields})

    except Exception as e:
        import traceback
        traceback.print_exc()

    # 2️⃣ Deterministic Architecture Tickets
    infra_plan = deterministic_architecture_plan(architecture)

    for epic in infra_plan.get("epics", []):

        flat_tickets.append({
            "fields": {
                "project": {"key": project_key},
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
                    "project": {"key": project_key},
                    "summary": ticket["description"],
                    "description": ticket["description"],
                    "issuetype": {"id": issue_types[ticket["type"]]},
                    "priority": {"id": priorities["High"]},
                    "labels": [ticket["layer"]]
                }
            })

    return {
        "project": project_key,
        "sprint_duration": "2 weeks",
        "tickets": flat_tickets
    }