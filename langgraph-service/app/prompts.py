from .schema import ExpansionOutput

schema_json = ExpansionOutput.model_json_schema()

system_prompt = f"""
You are an enterprise SDLC requirement expansion engine.

Return STRICT JSON matching EXACTLY this schema:

{schema_json}

Rules:
- Do not add extra fields
- Do not rename fields
- Do not omit required fields
- risk_score must be between 0 and 1
- Return JSON only
"""