from typing import List
from pydantic import BaseModel, Field, validator
import re 
import os
import json

from groq import Groq
import os

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# =========================
# Pydantic Models
# =========================

class Story(BaseModel):
    title: str
    description: str
    story_points: int
    acceptance_criteria: List[str]=[]

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
Consolidate everything into exactly 3 broad modules that together cover ALL functionality.
Do not lose any requirement — every feature must belong to one of the modules
Return strictly JSON array of module names.
No explanation.

PRD:
{prd_text}
"""

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
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

Generate exactly 1 comprehensive user story that covers all work in this module.
Return strictly JSON array of objects:
[
 {{
   "title": "...",
   "description": "...",
   "story_points": 3,
   "acceptance_criteria": [
      "criterion 1",
      "criterion 2"
   ]
 }}
]

No explanation.
PRD context:
{prd_text}
"""

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )

    content = response.choices[0].message.content.strip()
    

# Strip markdown fences
    if content.startswith("```"):
       content = re.sub(r"```(?:json)?", "", content).strip().strip("```").strip()

    try:
        raw_stories = json.loads(content)
        
    
        if not isinstance(raw_stories, list):
           raw_stories = [raw_stories]
    
        stories = []
        for s in raw_stories:
            try:
                stories.append(Story(**s))
            except Exception as e:
                
                print(f"BAD_STORY: {s}")
            # Add with defaults instead of failing
                stories.append(Story(
                title=s.get("title", "Untitled"),
                description=s.get("description", ""),
                story_points=min(max(s.get("story_points", 3), 1), 8),
                acceptance_criteria=s.get("acceptance_criteria", [])
            ))
    
        if not stories:
           raise ValueError(f"Invalid stories generated for module")
    
        return stories

    except json.JSONDecodeError as e:
           print(f"JSON_PARSE_ERROR: {e}, content: '{content[:200]}'")
           raise ValueError(f"Invalid stories generated for module")


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