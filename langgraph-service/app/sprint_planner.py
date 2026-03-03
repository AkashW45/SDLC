from typing import List
from pydantic import BaseModel, Field, validator

import os
import json

from cerebras.cloud.sdk import Cerebras


client = Cerebras(api_key=os.getenv("CEREBRAS_API_KEY"))


# =========================
# Pydantic Models
# =========================

class Story(BaseModel):
    title: str
    description: str
    story_points: int

    @validator("story_points")
    def validate_story_points(cls, v):
        if v < 1 or v > 8:
            raise ValueError("Story points must be between 1 and 8")
        return v


class Epic(BaseModel):
    title: str
    description: str
    stories: List[Story]

    @validator("stories")
    def validate_stories(cls, v):
        if not v:
            raise ValueError("Each epic must have at least one story")
        return v


class SprintPlan(BaseModel):
    project: str
    sprint_duration: str
    epics: List[Epic]

    @validator("epics")
    def validate_epics(cls, v):
        if not v:
            raise ValueError("Sprint plan must contain at least one epic")
        return v


# =========================
# LLM Helpers
# =========================

def extract_modules_from_prd(prd_text: str) -> List[str]:
    prompt = f"""
Extract main functional modules from this PRD.
Return strictly JSON array of module names.
No explanation.

PRD:
{prd_text}
"""

    response = client.chat.completions.create(
        model="gpt-oss-120b",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )

    content = response.choices[0].message.content.strip()

    try:
        modules = json.loads(content)
        if not isinstance(modules, list) or not modules:
            raise ValueError("Invalid module extraction")
        return modules
    except Exception:
        raise ValueError("Failed to extract modules from PRD")


def generate_stories_for_module(module_name: str, prd_text: str):
    prompt = f"""
You are a senior Scrum planner.

For module: {module_name}

Generate 3-6 user stories.
Return strictly JSON array of objects:
[
  {{
    "title": "...",
    "description": "...",
    "story_points": integer 1-8
  }}
]

No explanation.
PRD context:
{prd_text}
"""

    response = client.chat.completions.create(
        model="gpt-oss-120b",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )

    content = response.choices[0].message.content.strip()

    try:
        stories_raw = json.loads(content)
        return [Story(**story) for story in stories_raw]
    except Exception:
        raise ValueError(f"Invalid stories generated for module {module_name}")


# =========================
# Main Planner
# =========================

def generate_sprint_plan(prd_text: str, project_key: str = "DEV") -> SprintPlan:
    modules = extract_modules_from_prd(prd_text)

    epics = []

    for module in modules:
        stories = generate_stories_for_module(module, prd_text)

        epic = Epic(
            title=module,
            description=f"Epic covering {module} functionality",
            stories=stories
        )

        epics.append(epic)

    sprint_plan = SprintPlan(
        project=project_key,
        sprint_duration="2 weeks",
        epics=epics
    )

    return sprint_plan