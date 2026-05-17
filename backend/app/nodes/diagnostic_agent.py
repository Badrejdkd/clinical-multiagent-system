from __future__ import annotations
import os
import logging
from langchain_openai import ChatOpenAI
from langgraph.types import interrupt
from app.state import MedicalState
from app.tools.care_tools import recommend_interim_care
from dotenv import load_dotenv


logger = logging.getLogger(__name__)
load_dotenv()  # ← forcer le chargement ici aussi


PATIENT_QUESTIONS = [
    "Quels sont vos symptômes principaux et comment les décririez-vous ?",
    "Depuis combien de temps ressentez-vous ces symptômes (heures, jours, semaines) ?",
    "Avez-vous de la fièvre, des frissons, des nausées ou d'autres signes associés ?",
    "Avez-vous des antécédents médicaux importants ou des allergies connues ?",
    "Prenez-vous actuellement des médicaments ou avez-vous un traitement en cours ?",
]


def _get_llm() -> ChatOpenAI:
    load_dotenv()
    api_key = os.environ.get("OPENAI_API_KEY", "")
    return ChatOpenAI(
        model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        api_key=api_key,
        max_tokens=1024,
        temperature=0.3,
    )


def _generate_diagnostic_summary(patient_info: str, qa: list[dict]) -> str:
    """Génère une synthèse clinique préliminaire via OpenAI."""
    api_key = os.environ.get("OPENAI_API_KEY", "")

    # ── Vérification clé API ──────────────────────────────────────────────────
    if not api_key or "XXXX" in api_key or len(api_key) < 20:
        qa_text = "\n".join(f"  Q{i+1}: {item['answer']}" for i, item in enumerate(qa))
        return (
            "⚠️ [Mode sans LLM — clé OPENAI_API_KEY manquante dans .env]\n\n"
            f"Motif : {patient_info}\n\nDonnées collectées :\n{qa_text}\n\n"
            "Ajoutez OPENAI_API_KEY=sk-... dans le fichier .env "
            "puis redémarrez le backend."
        )

    # ── Appel LLM ────────────────────────────────────────────────────────────
    try:
        llm = _get_llm()
        qa_text = "\n".join(
            f"Q{i+1}: {item['question']}\nR: {item['answer']}"
            for i, item in enumerate(qa)
        )
        prompt = f"""Tu es un assistant médical académique.
Sur la base des informations suivantes recueillies auprès d'un patient,
rédige une synthèse clinique préliminaire CONCISE (150-200 mots) en français.

Motif de consultation : {patient_info}

Questions / Réponses :
{qa_text}

IMPORTANT : Utilise uniquement les termes "orientation clinique préliminaire"
et "synthèse clinique". Ne pose PAS de diagnostic définitif.
Mentionne les signes d'alarme (red flags) si présents.
"""
        response = llm.invoke(prompt)
        return response.content

    except Exception as exc:
        logger.error("OpenAI summary failed: %s", exc, exc_info=True)
        qa_text = "\n".join(f"  - {item['question']} → {item['answer']}" for item in qa)
        return (
            f"⚠️ [Erreur OpenAI : {exc}]\n\n"
            f"Motif : {patient_info}\n\nDonnées collectées :\n{qa_text}\n\n"
            "Vérifiez votre clé OPENAI_API_KEY et votre connexion."
        )


# ── Node ──────────────────────────────────────────────────────────────────────

def diagnostic_agent(state: MedicalState) -> dict:
    """
    Pose 5 questions au patient via interrupt(), puis génère la synthèse
    clinique préliminaire et la recommandation intermédiaire.
    """
    qa: list[dict] = list(state.get("questions_and_answers", []))
    q_idx = len(qa)

    # ── Poser la prochaine question ───────────────────────────────────────────
    if q_idx < len(PATIENT_QUESTIONS):
        question = PATIENT_QUESTIONS[q_idx]

        answer: str = interrupt(
            {
                "type": "patient_question",
                "question": question,
                "question_number": q_idx + 1,
                "total_questions": len(PATIENT_QUESTIONS),
            }
        )

        qa.append({"question": question, "answer": str(answer).strip()})
        new_count = len(qa)

        if new_count < len(PATIENT_QUESTIONS):
            return {
                "questions_and_answers": qa,
                "question_count": new_count,
            }

    # ── Toutes les réponses collectées → générer les sorties ─────────────────
    patient_info = state.get("patient_initial_info", "Non précisé")

    logger.info("5 questions complètes. Génération de la synthèse...")
    summary = _generate_diagnostic_summary(patient_info, qa)

    logger.info("Synthèse générée. Recommandation intermédiaire...")
    interim = recommend_interim_care(qa)

    logger.info("Terminé. Routage vers physician_review.")
    return {
        "questions_and_answers": qa,
        "question_count": len(qa),
        "diagnostic_summary": summary,
        "interim_care": interim,
        "next": "physician_review",
    }


def route_after_diagnostic(state: MedicalState) -> str:
    """Boucle vers diagnostic_agent jusqu'à 5 réponses collectées."""
    qa = state.get("questions_and_answers", [])
    if len(qa) < 5 and not state.get("diagnostic_summary"):
        return "diagnostic_agent"
    return "supervisor"
