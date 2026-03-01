import os
import json
import time
import uuid
import datetime
from typing import TypedDict

from openai import OpenAI, RateLimitError
from langgraph.graph import StateGraph


# ==========================================================
# Graph State
# ==========================================================

class GraphState(TypedDict, total=False):
    requirement: str
    blueprint: dict
    artifacts: dict
    risk_score: float
    governance: dict
    enforcement: dict


# ==========================================================
# OpenAI Client
# ==========================================================

def get_client():
    return OpenAI(
        api_key=os.getenv("CEREBRAS_API_KEY"),
        base_url="https://api.cerebras.ai/v1"
    )


# ==========================================================
# Generic LLM JSON Caller
# ==========================================================

def call_llm_json(system_prompt: str, user_prompt: str):
    max_retries = 3
    client = get_client()

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="gpt-oss-120b",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )

            return json.loads(response.choices[0].message.content)

        except RateLimitError:
            wait = 2 ** attempt
            print(f"Rate limited. Retrying in {wait}s")
            time.sleep(wait)

    raise Exception("LLM failed after retries")



# ==========================================================
# PASS 1 — SDLC Blueprint Node
# ==========================================================

def sdlc_plan_node(state: GraphState):

    system_prompt = system_prompt = """
You are a senior enterprise solution architect.

Given a product requirement, produce a structured SDLC blueprint.

Respond ONLY in strict JSON with EXACTLY this structure:

{
  "business_context": {
    "summary": ""
  },
  "system_overview": {
    "purpose": "",
    "scope": ""
  },
  "high_level_architecture": {
    "components": [
      {
        "name": "",
        "type": "",
        "description": ""
      }
    ],
    "interactions": [
      {
        "source": "",
        "target": "",
        "protocol": ""
      }
    ]
  },
  "data_entities": [
    {
      "name": "",
      "description": ""
    }
  ],
  "risk_indicators": [],
  "complexity_score": 0.0,
  "compliance_flags": []
}

Rules:
- components MUST be objects (not strings)
- interactions MUST reference component names exactly
- Do NOT add extra fields
- Do NOT rename fields
- Return JSON only
"""

    user_prompt = f"""
Requirement:
{state["requirement"]}
"""

    blueprint = call_llm_json(system_prompt, user_prompt)

    return {"blueprint": blueprint}


# ==========================================================
# PASS 2 — Artifact Generation Node
# ==========================================================

def sdlc_build_node(state: GraphState):

    system_prompt = """
You are an AI SDLC compiler.

Given a structured system blueprint, generate full SDLC artifacts.

Respond ONLY in JSON:

{
  "brd": {},
  "prd": {},
  "technical_architecture": {},
  "mermaid_diagram": "",
  "data_model_sql": "",
  "sprint_plan": [],
  "code_bundle": {
      "backend": "",
      "frontend": "",
      "database": ""
  },
  "test_suite": "",
  "release_runbook": "",
  "deployment_plan": {}
}
"""

    user_prompt = f"""
Blueprint:
{json.dumps(state["blueprint"], indent=2)}
"""

    artifacts = call_llm_json(system_prompt, user_prompt)
    from .diagram_generator import generate_mermaid_from_graph

    architecture_graph = state["blueprint"]["high_level_architecture"]

    deterministic_mermaid = generate_mermaid_from_graph(architecture_graph)

    artifacts["mermaid_diagram"] = deterministic_mermaid

    return {"artifacts": artifacts}


# ==========================================================
# Deterministic Risk Engine
# ==========================================================

def risk_compute_node(state: GraphState):

    blueprint = state["blueprint"]

    score = 0.0

    # Compliance risk weight
    if "PCI-DSS" in blueprint.get("compliance_flags", []):
        score += 0.4

    if "GDPR" in blueprint.get("compliance_flags", []):
        score += 0.2

    # Complexity factor
    score += blueprint.get("complexity_score", 0.0) * 0.3

    score = min(score, 1.0)

    return {"risk_score": score}


# ==========================================================
# Governance Node
# ==========================================================

def governance_node(state: GraphState):

    maturity = 3

    if state["risk_score"] > 0.8:
        maturity = 2

    governance = {
        "maturity_level": maturity,
        "review_required": state["risk_score"] > 0.7
    }

    return {"governance": governance}


# ==========================================================
# Enforcement Node
# ==========================================================

def enforcement_node(state: GraphState):

    actions = []

    if state["risk_score"] >= 0.8:
        actions.append("CREATE_JIRA")

    if state["governance"]["review_required"]:
        actions.append("ARCHITECT_REVIEW")

    enforcement = {
        "actions": actions,
        "approved_for_deployment": len(actions) == 0
    }

    return {"enforcement": enforcement}


# ==========================================================
# Audit Logging
# ==========================================================

def log_audit(state: GraphState):

    record = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "requirement": state["requirement"],
        "risk_score": state["risk_score"],
        "governance": state["governance"],
        "enforcement": state["enforcement"]
    }

    with open("audit_log.jsonl", "a") as f:
        f.write(json.dumps(record) + "\n")


def audit_node(state: GraphState):
    log_audit(state)
    return state


# ==========================================================
# Build Graph
# ==========================================================

def build_graph():
    builder = StateGraph(GraphState)

    builder.add_node("plan", sdlc_plan_node)
    builder.add_node("build", sdlc_build_node)
    builder.add_node("risk", risk_compute_node)
    builder.add_node("governance", governance_node)
    builder.add_node("enforce", enforcement_node)
    builder.add_node("audit", audit_node)

    builder.set_entry_point("plan")

    builder.add_edge("plan", "build")
    builder.add_edge("build", "risk")
    builder.add_edge("risk", "governance")
    builder.add_edge("governance", "enforce")
    builder.add_edge("enforce", "audit")

    builder.set_finish_point("audit")

    return builder.compile()