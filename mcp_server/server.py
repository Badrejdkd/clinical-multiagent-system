"""
mcp_server/server.py
────────────────────
Medical MCP Server — exposes clinical reference tools.

This server implements a simplified HTTP/JSON version of the MCP protocol
so it can be consumed both by the backend MCPClient and by any MCP-compatible
client (LangGraph Studio, Claude Desktop, etc.).

Tools exposed:
  • get_medical_guidelines(symptom)   → clinical guidelines for a symptom
  • check_red_flags(symptoms_text)    → detect emergency red flags in text
  • list_drugs_interactions(drugs)    → basic interaction warnings

Run:
    cd mcp_server
    python server.py              # default port 8001
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Medical MCP Server",
    description="MCP-compatible server exposing medical reference tools",
    version="1.0.0",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── Knowledge base (embedded for zero-dependency setup) ───────────────────────

GUIDELINES_DB: dict[str, str] = {
    "fièvre": (
        "Fièvre (T° ≥ 38 °C) : surveiller toutes les 4 h. "
        "Antipyrétiques (paracétamol 1 g/6 h max) si inconfort. "
        "Hydratation ++. Consulter si T° > 39,5 °C > 48 h ou enfant < 3 mois."
    ),
    "toux": (
        "Toux aiguë : généralement virale. "
        "Repos, hydratation, éviter irritants (tabac). "
        "Sirop antitussif si toux sèche invalidante. "
        "Consulter si toux > 3 semaines, hémoptysie ou dyspnée."
    ),
    "douleur thoracique": (
        "⚠️ URGENCE POSSIBLE. Éliminer SCA (IDM), embolie pulmonaire. "
        "Appeler le 15 si douleur intense, irradiation bras/mâchoire, sueurs, malaise. "
        "ECG en urgence."
    ),
    "céphalée": (
        "Céphalée commune : antalgiques (paracétamol, ibuprofène), repos, hydratation. "
        "⚠️ Urgence si : céphalée en 'coup de tonnerre', raideur nuque, fièvre + purpura, "
        "déficit neurologique."
    ),
    "nausée": (
        "Nausées/vomissements : régime alimentaire léger (BRAT), hydratation orale fractionnée. "
        "Antiémétiques si besoin. Consulter si vomissements > 24 h ou signes de déshydratation."
    ),
    "diarrhée": (
        "Diarrhée aiguë : réhydratation orale prioritaire (SRO ou eau + sel + sucre). "
        "Éviter les antidiarrhéiques si fièvre élevée ou selles sanglantes. "
        "Consulter si > 3 jours ou signes de déshydratation sévère."
    ),
    "dyspnée": (
        "⚠️ Dyspnée sévère = urgence. "
        "Évaluer SpO2, fréquence respiratoire, signes de détresse. "
        "Causes : asthme, BPCO, EP, insuffisance cardiaque. Appeler le 15 si SpO2 < 92 %."
    ),
    "default": (
        "Recommandations générales : repos, hydratation (1,5-2 L/jour), "
        "surveillance des symptômes. Consulter un médecin si aggravation sous 48-72 h."
    ),
}

RED_FLAGS_LIST = [
    ("douleur thoracique", "URGENCE — Douleur thoracique : exclure SCA / EP"),
    ("essoufflement sévère", "URGENCE — Dyspnée sévère nécessite évaluation immédiate"),
    ("perte de connaissance", "URGENCE — Perte de connaissance : appeler le 15"),
    ("paralysie", "URGENCE — Déficit neurologique : AVC possible, appeler le 15"),
    ("convulsion", "URGENCE — Convulsion : appeler le 15"),
    ("saignement abondant", "URGENCE — Hémorragie : compression et appel du 15"),
    ("confusion soudaine", "URGENCE — Confusion aiguë : AVC ou encéphalopathie possible"),
    ("raideur de la nuque", "URGENCE — Méningisme : méningite possible"),
    ("purpura", "URGENCE — Purpura fébrile : purpura fulminans possible"),
]

INTERACTIONS_DB: dict[tuple[str, str], str] = {
    ("warfarine", "aspirine"): "Risque hémorragique majoré — surveillance INR renforcée.",
    ("ISRS", "tramadol"): "Risque de syndrome sérotoninergique — à éviter.",
    ("metformine", "alcool"): "Risque d'acidose lactique — éviter l'alcool.",
    ("ibuprofen", "aspirine"): "Association déconseillée — toxicité GI et rénale augmentée.",
}


# ── Pydantic request models ───────────────────────────────────────────────────

class ToolCallRequest(BaseModel):
    name: str
    arguments: dict[str, Any]


# ── Tool implementations ──────────────────────────────────────────────────────

def _get_medical_guidelines(symptom: str) -> str:
    symptom_lower = symptom.lower().strip()
    for key, value in GUIDELINES_DB.items():
        if key in symptom_lower or symptom_lower in key:
            return value
    return GUIDELINES_DB["default"]


def _check_red_flags(symptoms_text: str) -> str:
    text_lower = symptoms_text.lower()
    found = [msg for keyword, msg in RED_FLAGS_LIST if keyword in text_lower]
    if found:
        return "🚨 RED FLAGS DÉTECTÉS :\n" + "\n".join(f"  • {f}" for f in found)
    return "✅ Aucun signe d'alarme majeur détecté dans le texte fourni."


def _list_drug_interactions(drugs: str) -> str:
    drugs_lower = [d.strip().lower() for d in drugs.split(",")]
    warnings = []
    for (d1, d2), msg in INTERACTIONS_DB.items():
        if d1 in drugs_lower and d2 in drugs_lower:
            warnings.append(f"⚠️ {d1.capitalize()} + {d2.capitalize()} : {msg}")
    if not warnings:
        return f"Aucune interaction connue détectée pour : {drugs}."
    return "\n".join(warnings)


# ── MCP endpoints ─────────────────────────────────────────────────────────────

@app.get("/tools")
def list_tools():
    """MCP: list available tools."""
    return {
        "tools": [
            {
                "name": "get_medical_guidelines",
                "description": "Retourne les recommandations cliniques pour un symptôme donné.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"symptom": {"type": "string"}},
                    "required": ["symptom"],
                },
            },
            {
                "name": "check_red_flags",
                "description": "Détecte les signes d'alarme (red flags) dans un texte de symptômes.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"symptoms_text": {"type": "string"}},
                    "required": ["symptoms_text"],
                },
            },
            {
                "name": "list_drug_interactions",
                "description": "Vérifie les interactions médicamenteuses connues.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"drugs": {"type": "string", "description": "Liste séparée par virgules"}},
                    "required": ["drugs"],
                },
            },
        ]
    }


@app.post("/tools/call")
def call_tool(req: ToolCallRequest):
    """MCP: call a specific tool."""
    if req.name == "get_medical_guidelines":
        result = _get_medical_guidelines(req.arguments.get("symptom", ""))
    elif req.name == "check_red_flags":
        result = _check_red_flags(req.arguments.get("symptoms_text", ""))
    elif req.name == "list_drug_interactions":
        result = _list_drug_interactions(req.arguments.get("drugs", ""))
    else:
        raise HTTPException(status_code=404, detail=f"Tool '{req.name}' not found.")

    return {"content": [{"type": "text", "text": result}]}


@app.get("/health")
def health():
    return {"status": "ok", "service": "medical-mcp-server"}


if __name__ == "__main__":
    port = int(os.environ.get("MCP_PORT", 8001))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)
