# services/agent_service.py

def call_agent_safe(agent, context: dict) -> dict:
    """
    AI agent is allowed to interpret, not invent.
    """
    if agent is None:
        return {}

    prompt = f"""
    You are a pharmaceutical domain assistant.

    You may:
    - Classify drug class
    - Explain formulation (salt vs prodrug vs base)
    - Identify strategic or lifecycle risks

    You may NOT:
    - Invent FDA approvals
    - Modify dosage forms
    - Add regulatory claims

    Context:
    {context}
    """

    try:
        response = agent.invoke(prompt)
        return response if isinstance(response, dict) else {}
    except Exception:
        return {}
