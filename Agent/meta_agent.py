# Agent/meta_agent.py

from typing import Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

# Agent/meta_agent.py

from typing import Dict, Any
import json
import time


# ============================
# Agent Builder (SAFE)
# ============================
def build_agent(llm):
    """
    Returns a callable agent function.
    No LangChain AgentExecutor.
    No JsonOutputParser.
    Never blocks.
    """

    def agent_fn(context: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"""
You are a pharmaceutical domain expert.

STRICT RULES:
- Do NOT invent FDA approvals, patents, or exclusivities
- Do NOT change dosage form or route
- Only interpret the given context
- If unsure, return "Unknown"

Return STRICT JSON ONLY:
{{
  "drug_class": "...",
  "formulation_type": "...",
  "risk_flags": ["..."]
}}

Context:
Drug: {context.get("drug")}
Route: {context.get("route")}
Dosage form: {context.get("dosage_form")}
Ingredient: {context.get("ingredient")}
Known formulation: {context.get("formulation_type")}
"""

        try:
            start = time.time()

            # ---- HARD TIMEOUT GUARD ----
            response = llm.invoke(prompt)

            elapsed = time.time() - start
            if elapsed > 20:
                return {
                    "drug_class": "Unknown",
                    "formulation_type": "Unknown",
                    "risk_flags": ["AI timeout exceeded"]
                }

            content = getattr(response, "content", None)
            if not content:
                return {}

            # ---- SAFE JSON PARSE ----
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                # Fallback: return raw text safely
                return {
                    "drug_class": "Unknown",
                    "formulation_type": "Unknown",
                    "risk_flags": [content[:300]]
                }

        except Exception as e:
            return {
                "drug_class": "Unknown",
                "formulation_type": "Unknown",
                "risk_flags": [f"AI error: {str(e)}"]
            }

    return agent_fn


# ============================
# Safe Invocation Wrapper
# ============================
def ask_meta_agent(agent, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Never blocks. Never crashes.
    """
    if agent is None:
        return {}

    return agent(context)

def _build_context_prompt(context: Dict[str, Any]) -> str:
    return f"""
Drug: {context.get("drug")}
Route: {context.get("route")}
Dosage form: {context.get("dosage_form")}
Ingredient: {context.get("ingredient")}
Known formulation: {context.get("formulation_type")}

Tasks:
1. Classify drug class
2. Confirm formulation type
3. Identify high-level strategic risks
"""
