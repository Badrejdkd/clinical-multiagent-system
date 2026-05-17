from typing import Annotated, List, Dict, Optional
from typing_extensions import TypedDict, Literal
from langgraph.graph.message import add_messages


class MedicalState(TypedDict, total=False):
    """Shared state for the medical multi-agent workflow."""

    # LangChain messages (conversation history)
    messages: Annotated[list, add_messages]

    # Routing: which node the Supervisor should dispatch to next
    next: Literal["diagnostic_agent", "physician_review", "report_agent", "FINISH"]

    # Patient initial complaint
    patient_initial_info: str

    # Q&A collected from the patient (list of {"question": ..., "answer": ...})
    questions_and_answers: List[Dict[str, str]]

    # Number of questions already answered (0-5)
    question_count: int

    # Outputs produced by the DiagnosticAgent
    diagnostic_summary: str          # Preliminary clinical synthesis
    interim_care: str                # Intermediate care recommendation

    # Output provided by the physician (Human-in-the-Loop)
    physician_treatment: str

    # Final structured report produced by the ReportAgent
    final_report: str
