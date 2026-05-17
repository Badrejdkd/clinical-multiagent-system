"""
Tools related to patient interaction.

These are plain Python functions — they are called directly inside
diagnostic_agent.py rather than through LangChain tool-calling,
because the interrupt() mechanism must run inside a LangGraph node.
"""
from __future__ import annotations


def ask_patient(question: str, question_number: int, total: int = 5) -> dict:
    """
    Build the interrupt payload that is sent to the frontend when the
    DiagnosticAgent needs a patient answer.

    Returns a dict that is passed directly to interrupt().
    """
    return {
        "type": "patient_question",
        "question": question,
        "question_number": question_number,
        "total_questions": total,
    }
