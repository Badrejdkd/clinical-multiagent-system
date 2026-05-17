"""
Tools that produce intermediate care recommendations.

These are rule-based to remain fast and deterministic.
They complement (but do not replace) the LLM-generated synthesis.
"""
from __future__ import annotations

# Keywords that trigger each recommendation category
_RED_FLAGS = [
    "douleur thoracique", "chest pain", "essoufflement sévère",
    "perte de connaissance", "paralysie", "troubles de la vision",
    "saignement abondant", "convulsion", "confusion soudaine",
    "douleur abdominale intense", "difficulté à respirer",
]

_FEVER_KEYWORDS = ["fièvre", "température", "38", "39", "40", "frissons"]
_RESP_KEYWORDS = ["toux", "gorge", "nez", "rhinite", "rhume", "expectorations"]
_DIGESTIVE_KEYWORDS = ["nausée", "vomissement", "diarrhée", "douleur abdominale", "estomac"]


def _lower_all(qa: list[dict]) -> str:
    return " ".join(
        (item.get("answer", "") + " " + item.get("question", "")).lower()
        for item in qa
    )


def recommend_interim_care(qa: list[dict]) -> str:
    """
    Rule-based intermediate care recommendation.

    Analyses patient answers and returns a structured recommendation string.
    """
    text = _lower_all(qa)

    recommendations: list[str] = []
    urgency = "normale"

    # ── Red flags ────────────────────────────────────────────────────────────
    found_flags = [f for f in _RED_FLAGS if f in text]
    if found_flags:
        urgency = "URGENTE"
        recommendations.append(
            "🚨 SIGNES D'ALARME DÉTECTÉS — Consultation médicale urgente recommandée "
            "(services d'urgence si nécessaire)."
        )

    # ── Fever ─────────────────────────────────────────────────────────────────
    if any(kw in text for kw in _FEVER_KEYWORDS):
        recommendations.append(
            "🌡️ Fièvre possible : surveiller la température toutes les 4 h, "
            "maintenir une bonne hydratation, antipyrétiques si T° > 38,5 °C "
            "(selon avis médical)."
        )

    # ── Respiratory ───────────────────────────────────────────────────────────
    if any(kw in text for kw in _RESP_KEYWORDS):
        recommendations.append(
            "😷 Symptômes respiratoires : repos à domicile, hydratation abondante, "
            "aération des pièces, éviter les contacts rapprochés."
        )

    # ── Digestive ─────────────────────────────────────────────────────────────
    if any(kw in text for kw in _DIGESTIVE_KEYWORDS):
        recommendations.append(
            "🥤 Troubles digestifs : régime alimentaire léger, hydratation (eau, bouillons), "
            "éviter les aliments irritants."
        )

    # ── General advice (always included) ─────────────────────────────────────
    recommendations.append(
        "💧 Recommandations générales : repos suffisant, hydratation adéquate "
        "(1,5-2 L d'eau/jour), surveillance de l'évolution des symptômes."
    )
    recommendations.append(
        "📞 Consulter rapidement un médecin en cas d'aggravation, de nouveaux symptômes "
        "ou si l'état ne s'améliore pas sous 48-72 h."
    )

    header = f"[Urgence : {urgency}]\n\n" if urgency == "URGENTE" else ""
    return header + "\n\n".join(recommendations)
