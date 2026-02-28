import os
import json
import time
import uuid
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


# ----------------------------
# Node 4: Audit
# ----------------------------

def audit_node(state: GraphState):
    log_audit(state["requirement"], state["final"])
    return {
        "final": state["final"]
    }


# ----------------------------
# Build Graph
# ----------------------------

def build_graph():
    builder = StateGraph(GraphState)

    builder.add_node("expand", expand_node)
    builder.add_node("compliance_enrich", compliance_enrich_node)
    builder.add_node("risk_compute", risk_compute_node)
    builder.add_node("audit", audit_node)

    builder.set_entry_point("expand")

    builder.add_edge("expand", "compliance_enrich")
    builder.add_edge("compliance_enrich", "risk_compute")
    builder.add_edge("risk_compute", "audit")

    builder.set_finish_point("audit")

    return builder.compile()