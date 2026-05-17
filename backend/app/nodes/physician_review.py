from __future__ import annotations
from langgraph.types import interrupt
from app.state import MedicalState


def physician_review(state: MedicalState) -> dict:
    """
    Human-in-the-Loop: pauses the graph so the treating physician can review
    the clinical synthesis and interim recommendation, then enter a treatment
    plan or conduct to follow.
    """
    treatment: str = interrupt(
        {
            "type": "physician_review",
            "diagnostic_summary": state.get("diagnostic_summary", ""),
            "interim_care": state.get("interim_care", ""),
            "patient_initial_info": state.get("patient_initial_info", ""),
            "questions_and_answers": state.get("questions_and_answers", []),
        }
    )

    return {
        "physician_treatment": str(treatment).strip(),
        "next": "report_agent",
    }
