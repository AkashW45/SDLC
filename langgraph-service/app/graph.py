import os
import json
import time
import uuid
import requests
import datetime
from typing import TypedDict

from openai import OpenAI, RateLimitError
from langgraph.graph import StateGraph
from .schema import ExpansionOutput
from .prompts import system_prompt


# ----------------------------
# Graph State
# ----------------------------

class GraphState(TypedDict, total=False):
    requirement: str
    expanded: dict
    enriched: dict
    final: dict


# ----------------------------
# OpenAI Client (No global side effects)
# ----------------------------

def get_client():
    return OpenAI(
        api_key=os.getenv("CEREBRAS_API_KEY"),
        base_url="https://api.cerebras.ai/v1"
    )


# ----------------------------
# LLM Call
# ----------------------------



def call_llm(requirement: str):
    max_retries = 3
    client = get_client()   # ← THIS LINE FIXES IT

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="gpt-oss-120b",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": requirement}
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )

            return response.choices[0].message.content

        except RateLimitError:
            wait = 2 ** attempt
            print(f"Rate limited. Retrying in {wait} seconds...")
            time.sleep(wait)

    raise Exception("LLM failed after retries.")


# ----------------------------
# Node 1: Expand Requirement
# ----------------------------

def expand_node(state: GraphState):
    raw_output = call_llm(state["requirement"])
    parsed = json.loads(raw_output)

    validated = ExpansionOutput.model_validate(parsed)

    return {
        "expanded": validated.model_dump()
    }


# ----------------------------
# Node 2: Compliance Enrichment
# ----------------------------

def compliance_enrich_node(state: GraphState):
    data = dict(state["expanded"])  # prevent mutation

    tags = set(data["compliance_tags"])

    # Deterministic compliance inference example
    if "credit" in state["requirement"].lower():
        tags.add("PCI-DSS")

    data["compliance_tags"] = list(tags)

    return {
        "enriched": data
    }


# ----------------------------
# Deterministic Risk Engine
# ----------------------------

SEVERITY_WEIGHTS = {
    "critical": 0.3,
    "high": 0.2,
    "medium": 0.1,
    "low": 0.05
}

COMPLIANCE_WEIGHTS = {
    "PCI-DSS": 0.4,
    "GDPR": 0.2,
    "HIPAA": 0.3
}


def compute_risk(output: ExpansionOutput) -> float:
    score = 0.0

    # Compliance-based risk
    for tag in output.compliance_tags:
        if tag in COMPLIANCE_WEIGHTS:
            score += COMPLIANCE_WEIGHTS[tag]

    # Security severity-based risk
    for sec in output.security_requirements:
        severity = sec.severity.lower()
        if severity in SEVERITY_WEIGHTS:
            score += SEVERITY_WEIGHTS[severity]

    for threat in output.threats:
        severity = threat.severity.lower()
        if severity in SEVERITY_WEIGHTS:
           score += SEVERITY_WEIGHTS[severity]        

    return min(score, 1.0)


# ----------------------------
# Node 3: Risk Computation
# ----------------------------

def risk_compute_node(state: GraphState):
    data = state["enriched"]

    output = ExpansionOutput.model_validate(data)

    output.risk_score = compute_risk(output)

    return {
        "final": output.model_dump()
    }


def governance_node(state: GraphState):
    data = dict(state["final"])

    maturity = 1
    strengths = []
    gaps = []

    # Compliance signal
    if "PCI-DSS" in data.get("compliance_tags", []):
        maturity += 1
        strengths.append("PCI-DSS compliance defined")
    else:
        gaps.append("No formal compliance framework")

    # MFA
    if any("multi" in sr["description"].lower() for sr in data["security_requirements"]):
        maturity += 1
        strengths.append("Administrative MFA enforced")
    else:
        gaps.append("Missing MFA enforcement")

    # Monitoring
    if any("monitor" in comp["name"].lower() for comp in data["architecture"]):
        maturity += 1
        strengths.append("Operational monitoring defined")
    else:
        gaps.append("No monitoring layer")

    # Logging
    if any("audit" in sr["description"].lower() for sr in data["security_requirements"]):
        maturity += 1
        strengths.append("Audit logging defined")
    else:
        gaps.append("Audit logging not enforced")

    maturity = min(maturity, 5)

    data["governance"] = {
        "maturity_level": maturity,
        "strengths": strengths,
        "gaps": gaps
    }

    return {"final": data}
# ----------------------------
# Audit Logging
# ----------------------------

def log_audit(requirement: str, result: dict):
    record = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "requirement": requirement,
        "result": result
    }

    with open("audit_log.jsonl", "a") as f:
        f.write(json.dumps(record) + "\n")



def orchestration_node(state: GraphState):
    data = state["final"]

    webhook_url = os.getenv("N8N_WEBHOOK_URL")

    if webhook_url:
        try:
            requests.post(webhook_url, json=data, timeout=5)
        except Exception as e:
            print("Failed to call n8n:", e)

    return {"final": data}
# ----------------------------
# Node 4: Audit
# ----------------------------

def audit_node(state: GraphState):
    log_audit(state["requirement"], state["final"])
    return {
        "final": state["final"]
    }


def threat_model_node(state: GraphState):
    data = dict(state["enriched"])

    prompt = f"""
You are a security architect.

Perform STRIDE threat modeling.

Return ONLY a JSON array.

Example:
[
  {{
    "category": "Spoofing",
    "description": "...",
    "severity": "High"
  }}
]

No explanation.
No wrapper object.
Only the array.
"""

    raw = call_llm(prompt)

    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = []

    # If model wrapped it
    if isinstance(parsed, dict):
        if "threats" in parsed:
            parsed = parsed["threats"]
        else:
            parsed = []

    if not isinstance(parsed, list):
        parsed = []

    data["threats"] = parsed

    return {"enriched": data}



# ----------------------------
# Build Graph
# ----------------------------

def build_graph():
    builder = StateGraph(GraphState)

    builder.add_node("expand", expand_node)
    builder.add_node("compliance_enrich", compliance_enrich_node)
    builder.add_node("threat_model", threat_model_node)
    builder.add_node("risk_compute", risk_compute_node)
    builder.add_node("governance", governance_node)
    builder.add_node("orchestration", orchestration_node)
    builder.add_node("audit", audit_node)

    builder.set_entry_point("expand")

    builder.add_edge("expand", "compliance_enrich")
    builder.add_edge("compliance_enrich", "threat_model")
    builder.add_edge("threat_model", "risk_compute")
    builder.add_edge("risk_compute", "governance")
    builder.add_edge("governance", "orchestration")
    builder.add_edge("orchestration", "audit")

    builder.set_finish_point("audit")

    return builder.compile()