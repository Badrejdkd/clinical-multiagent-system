from __future__ import annotations
import os
import logging
from datetime import datetime
from langchain_openai import ChatOpenAI
from app.state import MedicalState

logger = logging.getLogger(__name__)


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        api_key=os.environ.get("OPENAI_API_KEY", ""),
        max_tokens=2048,
        temperature=0.3,
    )


def _build_qa_text(qa: list[dict]) -> str:
    return "\n".join(
        f"  Q{i+1}: {item['question']}\n  R: {item['answer']}"
        for i, item in enumerate(qa)
    )


def report_agent(state: MedicalState) -> dict:
    """Génère le rapport clinique structuré final via OpenAI."""
    now = datetime.now().strftime("%d/%m/%Y à %H:%M")
    qa_text = _build_qa_text(state.get("questions_and_answers", []))

    api_key = os.environ.get("OPENAI_API_KEY", "")

    # ── Fallback sans LLM ─────────────────────────────────────────────────────
    if not api_key or "XXXX" in api_key or len(api_key) < 20:
        final_report = f"""
╔══════════════════════════════════════════════════════════╗
║         RAPPORT CLINIQUE PRÉLIMINAIRE (Mode sans LLM)   ║
╚══════════════════════════════════════════════════════════╝

Date : {now}
Motif initial : {state.get('patient_initial_info', 'Non précisé')}

── ANAMNÈSE ──────────────────────────────────────────────
{qa_text}

── SYNTHÈSE CLINIQUE ─────────────────────────────────────
{state.get('diagnostic_summary', 'Non disponible')}

── RECOMMANDATION INTERMÉDIAIRE ──────────────────────────
{state.get('interim_care', 'Non disponible')}

── CONDUITE À TENIR (Médecin) ────────────────────────────
{state.get('physician_treatment', 'Non précisé')}

──────────────────────────────────────────────────────────
⚠️ Ce système ne remplace pas une consultation médicale.
   Rapport produit à titre académique uniquement.
"""
        return {"final_report": final_report.strip(), "next": "FINISH"}

    # ── Appel OpenAI ──────────────────────────────────────────────────────────
    try:
        llm = _get_llm()
        prompt = f"""Tu es un assistant médical académique.
Génère un rapport clinique structuré FINAL en français, basé sur les données suivantes.

=== DONNÉES DE CONSULTATION ===
Date : {now}
Motif initial : {state.get('patient_initial_info', 'Non précisé')}

Questions / Réponses patient :
{qa_text}

Synthèse clinique préliminaire :
{state.get('diagnostic_summary', '')}

Recommandation intermédiaire :
{state.get('interim_care', '')}

Conduite à tenir proposée par le médecin :
{state.get('physician_treatment', '')}

=== INSTRUCTIONS ===
Structure le rapport avec ces sections :
1. EN-TÊTE (date, motif de consultation)
2. ANAMNÈSE (résumé des réponses patient)
3. SYNTHÈSE CLINIQUE PRÉLIMINAIRE
4. RECOMMANDATION INTERMÉDIAIRE DE SOINS
5. CONDUITE À TENIR (traitement médecin)
6. CONCLUSION ET SUIVI

Termine OBLIGATOIREMENT par :
"⚠️ Ce système ne remplace pas une consultation médicale.
Ce rapport est produit à titre académique uniquement."
"""
        response = llm.invoke(prompt)
        return {"final_report": response.content, "next": "FINISH"}

    except Exception as exc:
        logger.error("OpenAI report generation failed: %s", exc, exc_info=True)
        fallback = (
            f"⚠️ [Erreur OpenAI : {exc}]\n\n"
            f"Date : {now}\nMotif : {state.get('patient_initial_info', '')}\n\n"
            f"Synthèse :\n{state.get('diagnostic_summary', '')}\n\n"
            f"Traitement médecin :\n{state.get('physician_treatment', '')}\n\n"
            "⚠️ Ce système ne remplace pas une consultation médicale."
        )
        return {"final_report": fallback, "next": "FINISH"}
