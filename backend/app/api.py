from __future__ import annotations
from dotenv import load_dotenv
load_dotenv()

import uuid
import logging
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langgraph.types import Command
from langgraph.checkpoint.memory import MemorySaver
from app.graph import build_graph

# Graph AVEC checkpointer pour FastAPI (différent du graph= pour Studio)
_graph = build_graph(checkpointer=MemorySaver())

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Système Multi-Agents Médical",
    description="Workflow d'orientation clinique basé sur LangGraph",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic models ───────────────────────────────────────────────────────────

class SessionResponse(BaseModel):
    thread_id: str
    message: str


class ConsultationStartRequest(BaseModel):
    thread_id: str
    patient_initial_info: str


class ResumeRequest(BaseModel):
    thread_id: str
    value: str


class ConsultationStatus(BaseModel):
    thread_id: str
    phase: str
    interrupt_data: Optional[dict]
    state: Optional[dict]
    is_complete: bool


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def _get_interrupt_data(thread_id: str) -> Optional[dict]:
    config = _make_config(thread_id)
    try:
        snapshot = _graph.get_state(config)
    except Exception:
        return None
    for task in snapshot.tasks:
        if task.interrupts:
            return task.interrupts[0].value
    return None


def _state_snapshot_to_dict(thread_id: str) -> dict:
    config = _make_config(thread_id)
    try:
        snapshot = _graph.get_state(config)
        return dict(snapshot.values) if snapshot else {}
    except Exception:
        return {}


def _derive_phase(interrupt_data: Optional[dict], state: dict) -> str:
    if not state.get("patient_initial_info"):
        return "intake"
    if interrupt_data is None:
        return "complete"
    t = interrupt_data.get("type", "")
    if t == "patient_question":
        return "patient_question"
    if t == "physician_review":
        return "physician_review"
    return "running"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/sessions/start", response_model=SessionResponse)
def create_session():
    thread_id = str(uuid.uuid4())
    logger.info("New session created: %s", thread_id)
    return SessionResponse(
        thread_id=thread_id,
        message="Session créée.",
    )


@app.post("/consultation/start", response_model=ConsultationStatus)
def start_consultation(req: ConsultationStartRequest):
    config = _make_config(req.thread_id)
    try:
        _graph.invoke(
            {"patient_initial_info": req.patient_initial_info},
            config,
        )
    except Exception as exc:
        logger.error("Graph invoke error: %s", exc, exc_info=True)

    interrupt_data = _get_interrupt_data(req.thread_id)
    state          = _state_snapshot_to_dict(req.thread_id)
    phase          = _derive_phase(interrupt_data, state)

    return ConsultationStatus(
        thread_id=req.thread_id,
        phase=phase,
        interrupt_data=interrupt_data,
        state=state,
        is_complete=(phase == "complete"),
    )


@app.post("/consultation/resume", response_model=ConsultationStatus)
def resume_consultation(req: ResumeRequest):
    config = _make_config(req.thread_id)

    state_before = _state_snapshot_to_dict(req.thread_id)
    if not state_before:
        raise HTTPException(status_code=404, detail="Session introuvable.")

    try:
        _graph.invoke(Command(resume=req.value), config)
    except Exception as exc:
        logger.error("Graph resume error: %s", exc, exc_info=True)

    interrupt_data = _get_interrupt_data(req.thread_id)
    state          = _state_snapshot_to_dict(req.thread_id)
    phase          = _derive_phase(interrupt_data, state)

    return ConsultationStatus(
        thread_id=req.thread_id,
        phase=phase,
        interrupt_data=interrupt_data,
        state=state,
        is_complete=(phase == "complete"),
    )


@app.get("/consultation/{thread_id}", response_model=ConsultationStatus)
def get_consultation_status(thread_id: str):
    interrupt_data = _get_interrupt_data(thread_id)
    state          = _state_snapshot_to_dict(thread_id)

    if not state:
        raise HTTPException(status_code=404, detail="Session introuvable.")

    phase = _derive_phase(interrupt_data, state)

    return ConsultationStatus(
        thread_id=thread_id,
        phase=phase,
        interrupt_data=interrupt_data,
        state=state,
        is_complete=(phase == "complete"),
    )


@app.get("/consultation/{thread_id}/report")
def get_report(thread_id: str):
    state = _state_snapshot_to_dict(thread_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session introuvable.")

    report = state.get("final_report")
    if not report:
        raise HTTPException(
            status_code=202,
            detail="Rapport pas encore disponible.",
        )

    return {
        "thread_id":          thread_id,
        "final_report":       report,
        "diagnostic_summary": state.get("diagnostic_summary"),
        "interim_care":       state.get("interim_care"),
        "physician_treatment": state.get("physician_treatment"),
    }


@app.get("/health")
def health():
    return {"status": "ok", "service": "medical-multiagent-backend"}