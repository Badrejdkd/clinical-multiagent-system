from __future__ import annotations
from app.state import MedicalState


def supervisor(state: MedicalState) -> dict:
    """
    Orchestrator: decides which node to run next based on the current state.
    - No diagnostic_summary yet  →  send to diagnostic_agent
    - No physician_treatment yet →  send to physician_review
    - No final_report yet        →  send to report_agent
    - Everything done            →  FINISH
    """
    if not state.get("diagnostic_summary"):
        return {"next": "diagnostic_agent"}

    if not state.get("physician_treatment"):
        return {"next": "physician_review"}

    if not state.get("final_report"):
        return {"next": "report_agent"}

    return {"next": "FINISH"}


def route_supervisor(state: MedicalState) -> str:
    """Conditional edge used by the graph to branch after supervisor."""
    return state.get("next", "diagnostic_agent")
