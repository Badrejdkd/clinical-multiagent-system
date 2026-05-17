from __future__ import annotations
from langgraph.graph import StateGraph, START, END
from app.state import MedicalState
from app.nodes.supervisor import supervisor, route_supervisor
from app.nodes.diagnostic_agent import diagnostic_agent, route_after_diagnostic
from app.nodes.physician_review import physician_review
from app.nodes.report_agent import report_agent


def build_graph(checkpointer=None):
    builder = StateGraph(MedicalState)
    builder.add_node("supervisor",       supervisor)
    builder.add_node("diagnostic_agent", diagnostic_agent)
    builder.add_node("physician_review", physician_review)
    builder.add_node("report_agent",     report_agent)
    builder.add_edge(START, "supervisor")
    builder.add_conditional_edges(
        "supervisor", route_supervisor,
        {"diagnostic_agent": "diagnostic_agent",
         "physician_review": "physician_review",
         "report_agent":     "report_agent",
         "FINISH":           END},
    )
    builder.add_conditional_edges(
        "diagnostic_agent", route_after_diagnostic,
        {"diagnostic_agent": "diagnostic_agent",
         "supervisor":       "supervisor"},
    )
    builder.add_edge("physician_review", "supervisor")
    builder.add_edge("report_agent",     "supervisor")
    if checkpointer:
        return builder.compile(checkpointer=checkpointer)
    return builder.compile()


graph = build_graph()