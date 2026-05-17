import os, time, requests, streamlit as st
from datetime import datetime

API_BASE = os.environ.get("API_BASE_URL", "http://localhost:8000")

st.set_page_config(page_title="Diagnostic Médical IA", page_icon="🏥", layout="wide")

st.markdown("""
<style>
[data-testid="stAppViewContainer"]{background:#f0f4f8}
.card{background:white;border-radius:12px;padding:1.5rem 2rem;margin-bottom:1.2rem;
      box-shadow:0 2px 10px rgba(0,0,0,.07);border-left:5px solid #2563eb}
.card-green{border-left-color:#16a34a}
.card-purple{border-left-color:#7c3aed}
.card-orange{border-left-color:#ea580c}
.qa-q{background:#eff6ff;border-radius:10px;padding:.7rem 1rem;margin:.4rem 0}
.qa-a{background:#f0fdf4;border-radius:10px;padding:.7rem 1rem;margin:.4rem 0 .8rem 2rem}
.legal{background:#fef3c7;border:1px solid #fbbf24;border-radius:8px;
       padding:.75rem 1.2rem;font-size:.85rem;color:#92400e;margin-top:1rem}
.report{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:2rem;
        font-family:'Courier New',monospace;font-size:.88rem;white-space:pre-wrap;
        line-height:1.6;max-height:600px;overflow-y:auto}
#MainMenu,footer{visibility:hidden}
</style>
""", unsafe_allow_html=True)

if "S" not in st.session_state:
    st.session_state.S = {
        "thread_id": None,
        "phase": "intake",
        "interrupt_data": None,
        "state": {},
        "error": None,
        "intake_text": "",
    }
S = st.session_state.S


def api(method, path, **kwargs):
    try:
        r = getattr(requests, method)(f"{API_BASE}{path}", timeout=60, **kwargs)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        S["error"] = f"❌ Backend inaccessible sur {API_BASE} — lancez uvicorn main:app --port 8000"
    except Exception as e:
        S["error"] = f"❌ Erreur {path}: {e}"
    return None


def sync(data):
    if not data:
        return
    S["thread_id"]      = data.get("thread_id",      S["thread_id"])
    S["phase"]          = data.get("phase",           S["phase"])
    S["interrupt_data"] = data.get("interrupt_data")
    S["state"]          = data.get("state",           {})


with st.sidebar:
    st.title("🏥 Diagnostic IA")
    st.divider()
    phases = [("intake","1. Motif"),("patient_question","2. Questions"),
              ("physician_review","3. Médecin"),("complete","4. Rapport")]
    order = [p[0] for p in phases]
    ci = order.index(S["phase"]) if S["phase"] in order else 0
    for i, (pid, label) in enumerate(phases):
        if   i < ci:  st.markdown(f"✅ {label}")
        elif i == ci: st.markdown(f"**▶️ {label}**")
        else:         st.markdown(f"<span style='color:#9ca3af'>○ {label}</span>", unsafe_allow_html=True)
    st.divider()
    if S["thread_id"]:
        st.caption(f"🔑 `{S['thread_id'][:8]}…`")
    qa_count = len(S["state"].get("questions_and_answers", []))
    if qa_count:
        st.caption(f"📋 {qa_count}/5 questions")
    st.divider()
    if st.button("🔄 Nouvelle consultation", use_container_width=True):
        st.session_state.S = {
            "thread_id": None, "phase": "intake",
            "interrupt_data": None, "state": {},
            "error": None, "intake_text": "",
        }
        st.rerun()
    st.caption("⚠️ Usage académique uniquement.")

if S["error"]:
    col_err, col_btn = st.columns([4, 1])
    with col_err:
        st.error(S["error"])
    with col_btn:
        if st.button("✖"):
            S["error"] = None
            st.rerun()


# ════════════════════════════════════════════════════════════════════════════════
# SCREEN 1 — INTAKE
# ════════════════════════════════════════════════════════════════════════════════
if S["phase"] == "intake":

    st.markdown('<div class="card"><h2 style="margin:0">🩺 Consultation Médicale Assistée par IA</h2></div>',
                unsafe_allow_html=True)

    col1, col2 = st.columns([3, 2])

    with col2:
        st.subheader("🧪 Cas de test")
        cases = {
            "Syndrome respiratoire": "Patient 28 ans, fièvre 38.8°C depuis 3 jours, toux sèche persistante.",
            "Cas avec red flags":    "Femme 55 ans, douleur thoracique irradiant vers le bras gauche, sueurs froides.",
            "Cas bénin":             "Enfant 8 ans, rhinite légère, pas de fièvre, état général conservé.",
        }
        for label, text in cases.items():
            if st.button(f"📋 {label}", use_container_width=True, key=f"cas_{label}"):
                S["intake_text"] = text
                st.rerun()

    with col1:
        with st.form("form_intake"):
            txt = st.text_area(
                "Décrivez les symptômes :",
                value=S["intake_text"],
                placeholder="Ex : Patient 35 ans, fièvre 38.5°C depuis 2 jours…",
                height=160,
            )
            go = st.form_submit_button("🚀 Démarrer", type="primary", use_container_width=True)

        st.markdown('<div class="legal">⚠️ Exercice académique uniquement.</div>', unsafe_allow_html=True)

        if go and txt.strip():
            if S["thread_id"] is None:
                with st.spinner("Démarrage…"):
                    sess = api("post", "/sessions/start")
                    if sess:
                        S["thread_id"] = sess["thread_id"]
                        data = api("post", "/consultation/start",
                                   json={"thread_id": S["thread_id"],
                                         "patient_initial_info": txt.strip()})
                        sync(data)
                if not S["error"]:
                    S["intake_text"] = ""
                    st.rerun()
                else:
                    S["thread_id"] = None
        elif go and not txt.strip():
            st.warning("Veuillez décrire les symptômes.")


# ════════════════════════════════════════════════════════════════════════════════
# SCREEN 2 — QUESTIONS PATIENT
# ════════════════════════════════════════════════════════════════════════════════
elif S["phase"] == "patient_question":

    idata    = S["interrupt_data"] or {}
    question = idata.get("question", "Question non disponible")
    q_num    = idata.get("question_number", 1)
    q_total  = idata.get("total_questions", 5)

    st.markdown(f'<div class="card"><h2 style="margin:0">💬 Question {q_num} / {q_total}</h2></div>',
                unsafe_allow_html=True)
    st.progress((q_num - 1) / q_total)

    col1, col2 = st.columns([3, 2])

    with col1:
        for item in S["state"].get("questions_and_answers", []):
            st.markdown(
                f'<div class="qa-q">🩺 <strong>{item["question"]}</strong></div>'
                f'<div class="qa-a">👤 {item["answer"]}</div>',
                unsafe_allow_html=True,
            )
        if S["state"].get("questions_and_answers"):
            st.divider()

        st.markdown(
            f'<div class="card card-purple"><p style="font-size:1.05rem;margin:0">{question}</p></div>',
            unsafe_allow_html=True,
        )

        with st.form(f"form_q{q_num}"):
            ans = st.text_area("Votre réponse :", placeholder="Décrivez avec précision…", height=120)
            send = st.form_submit_button("➡️ Répondre", type="primary", use_container_width=True)

        if send:
            if not ans.strip():
                st.warning("Veuillez entrer une réponse.")
            else:
                with st.spinner("Traitement de la réponse…"):
                    data = api("post", "/consultation/resume",
                               json={"thread_id": S["thread_id"], "value": ans.strip()})
                    sync(data)
                if not S["error"]:
                    st.rerun()

    with col2:
        st.subheader("📊 Progression")
        for i in range(1, q_total + 1):
            if   i < q_num:  st.markdown(f"✅ Question {i} — Répondue")
            elif i == q_num: st.markdown(f"**▶️ Question {i} — En cours**")
            else:             st.markdown(f"⬜ Question {i} — En attente")

        st.divider()
        st.subheader("💡 Conseils")
        tips = {
            1: ["Décrivez chaque symptôme séparément", "Notez l'intensité (léger/modéré/sévère)"],
            2: ["Précisez heures/jours/semaines", "Évolution : stable, aggravation ?"],
            3: ["Température si mesurée", "Fatigue, perte d'appétit…"],
            4: ["Maladies chroniques (diabète, HTA…)", "Allergies médicamenteuses"],
            5: ["Nom des médicaments si possible", "Automédication récente ?"],
        }
        for tip in tips.get(q_num, ["Répondez précisément."]):
            st.markdown(f"• {tip}")


# ════════════════════════════════════════════════════════════════════════════════
# SCREEN 3 — REVUE MÉDECIN
# ════════════════════════════════════════════════════════════════════════════════
elif S["phase"] == "physician_review":

    idata = S["interrupt_data"] or {}
    st.markdown('<div class="card card-green"><h2 style="margin:0">👨‍⚕️ Revue du Médecin Traitant</h2></div>',
                unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🔬 Synthèse Clinique")
        st.info(idata.get("diagnostic_summary", S["state"].get("diagnostic_summary", "Non disponible")))
        st.subheader("💊 Recommandation Intermédiaire")
        st.warning(idata.get("interim_care", S["state"].get("interim_care", "Non disponible")))

    with col2:
        st.subheader("📋 Récapitulatif Patient")
        motif = S["state"].get("patient_initial_info", "")
        if motif:
            st.markdown(f"**Motif :** {motif}")
        for item in S["state"].get("questions_and_answers", []):
            with st.expander(f"{item['question'][:55]}…"):
                st.write(item["answer"])

        st.subheader("✍️ Conduite à Tenir")
        with st.form("form_physician"):
            treat = st.text_area(
                "Traitement proposé :", height=160,
                placeholder="Ex: Paracétamol 1g x3/j, repos 3 jours, contrôle 48h…"
            )
            valid = st.form_submit_button("✅ Valider et générer le rapport",
                                          type="primary", use_container_width=True)

        if valid:
            if not treat.strip():
                st.warning("Veuillez saisir une conduite à tenir.")
            else:
                with st.spinner("Génération du rapport final…"):
                    data = api("post", "/consultation/resume",
                               json={"thread_id": S["thread_id"], "value": treat.strip()})
                    sync(data)
                if not S["error"]:
                    st.rerun()


# ════════════════════════════════════════════════════════════════════════════════
# SCREEN 4 — RAPPORT FINAL
# ════════════════════════════════════════════════════════════════════════════════
elif S["phase"] == "complete":

    st.markdown('<div class="card card-green"><h2 style="margin:0">📄 Rapport Clinique Final ✅</h2></div>',
                unsafe_allow_html=True)

    state = S["state"]
    tab1, tab2, tab3 = st.tabs(["📄 Rapport Complet", "📊 Données Détaillées", "💬 Q&A Patient"])

    with tab1:
        report = state.get("final_report", "Rapport non disponible.")
        st.markdown(f'<div class="report">{report}</div>', unsafe_allow_html=True)
        st.markdown('<div class="legal">⚠️ Ce système ne remplace pas une consultation médicale.</div>',
                    unsafe_allow_html=True)

        col_txt, col_pdf = st.columns(2)

        with col_txt:
            st.download_button(
                "⬇️ Télécharger (.txt)",
                data=report,
                file_name=f"rapport_clinique_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                mime="text/plain",
                use_container_width=True,
            )

        with col_pdf:
            try:
                from fpdf import FPDF
                import re

                def clean_text(text):
                    """Supprime les emojis et caractères non supportés par Helvetica."""
                    # Supprimer les emojis et symboles unicode
                    emoji_pattern = re.compile(
                        "["
                        u"\U0001F600-\U0001F64F"
                        u"\U0001F300-\U0001F5FF"
                        u"\U0001F680-\U0001F6FF"
                        u"\U0001F1E0-\U0001F1FF"
                        u"\U00002700-\U000027BF"
                        u"\U000024C2-\U0001F251"
                        u"\U0001F900-\U0001F9FF"
                        u"\U00002600-\U000026FF"
                        u"\U0001FA00-\U0001FA6F"
                        u"\U0001FA70-\U0001FAFF"
                        u"\u2640-\u2642"
                        u"\u2194-\u2199"
                        u"\u2300-\u23FF"
                        u"\u25A0-\u25FF"
                        u"\u2700-\u27BF"
                        "]+",
                        flags=re.UNICODE
                    )
                    text = emoji_pattern.sub("", text)
                    # Encoder en latin-1 en ignorant les caractères non supportés
                    text = text.encode("latin-1", errors="ignore").decode("latin-1")
                    return text.strip()

                pdf = FPDF()
                pdf.add_page()
                pdf.set_auto_page_break(auto=True, margin=15)
                pdf.set_margins(15, 20, 15)

                # En-tête
                pdf.set_font("Helvetica", "B", 14)
                pdf.set_text_color(37, 99, 235)
                pdf.cell(0, 10, "Rapport Clinique Preliminaire", align="C", new_x="LMARGIN", new_y="NEXT")
                pdf.set_draw_color(37, 99, 235)
                pdf.set_line_width(0.5)
                pdf.line(15, pdf.get_y(), 195, pdf.get_y())
                pdf.ln(4)

                # Date
                pdf.set_font("Helvetica", "I", 9)
                pdf.set_text_color(100, 100, 100)
                pdf.cell(0, 6, f"Genere le {datetime.now().strftime('%d/%m/%Y a %H:%M')}", align="R", new_x="LMARGIN", new_y="NEXT")
                pdf.ln(4)

                # Motif
                motif = clean_text(state.get("patient_initial_info", ""))
                if motif:
                    pdf.set_font("Helvetica", "B", 11)
                    pdf.set_text_color(255, 255, 255)
                    pdf.set_fill_color(37, 99, 235)
                    pdf.cell(0, 8, "  Motif de consultation", new_x="LMARGIN", new_y="NEXT", fill=True)
                    pdf.set_font("Helvetica", "", 10)
                    pdf.set_text_color(30, 30, 30)
                    pdf.set_fill_color(239, 246, 255)
                    pdf.multi_cell(0, 6, motif, fill=True)
                    pdf.ln(4)

                # Synthèse clinique
                summary = clean_text(state.get("diagnostic_summary", ""))
                if summary:
                    pdf.set_font("Helvetica", "B", 11)
                    pdf.set_text_color(255, 255, 255)
                    pdf.set_fill_color(37, 99, 235)
                    pdf.cell(0, 8, "  Synthese Clinique Preliminaire", new_x="LMARGIN", new_y="NEXT", fill=True)
                    pdf.set_font("Helvetica", "", 10)
                    pdf.set_text_color(30, 30, 30)
                    pdf.set_fill_color(240, 249, 255)
                    pdf.multi_cell(0, 6, summary, fill=True)
                    pdf.ln(4)

                # Recommandation intermédiaire
                interim = clean_text(state.get("interim_care", ""))
                if interim:
                    pdf.set_font("Helvetica", "B", 11)
                    pdf.set_text_color(255, 255, 255)
                    pdf.set_fill_color(234, 88, 12)
                    pdf.cell(0, 8, "  Recommandation Intermediaire", new_x="LMARGIN", new_y="NEXT", fill=True)
                    pdf.set_font("Helvetica", "", 10)
                    pdf.set_text_color(30, 30, 30)
                    pdf.set_fill_color(255, 247, 237)
                    pdf.multi_cell(0, 6, interim, fill=True)
                    pdf.ln(4)

                # Traitement médecin
                treatment = clean_text(state.get("physician_treatment", ""))
                if treatment:
                    pdf.set_font("Helvetica", "B", 11)
                    pdf.set_text_color(255, 255, 255)
                    pdf.set_fill_color(22, 163, 74)
                    pdf.cell(0, 8, "  Conduite a Tenir (Medecin)", new_x="LMARGIN", new_y="NEXT", fill=True)
                    pdf.set_font("Helvetica", "", 10)
                    pdf.set_text_color(30, 30, 30)
                    pdf.set_fill_color(240, 253, 244)
                    pdf.multi_cell(0, 6, treatment, fill=True)
                    pdf.ln(4)

                # Rapport complet
                clean_report = clean_text(report)
                if clean_report:
                    pdf.set_font("Helvetica", "B", 11)
                    pdf.set_text_color(255, 255, 255)
                    pdf.set_fill_color(71, 85, 105)
                    pdf.cell(0, 8, "  Rapport Final Complet", new_x="LMARGIN", new_y="NEXT", fill=True)
                    pdf.set_font("Helvetica", "", 9)
                    pdf.set_text_color(50, 50, 50)
                    pdf.set_fill_color(248, 248, 248)
                    pdf.multi_cell(0, 5, clean_report, fill=True)
                    pdf.ln(4)

                # Mention légale
                pdf.set_font("Helvetica", "I", 8)
                pdf.set_text_color(150, 100, 0)
                pdf.set_fill_color(254, 243, 199)
                pdf.multi_cell(0, 6,
                    "AVERTISSEMENT : Ce systeme ne remplace pas une consultation medicale. "
                    "Rapport produit a titre academique uniquement.",
                    fill=True
                )

                pdf_bytes = bytes(pdf.output())

                st.download_button(
                    "⬇️ Télécharger (.pdf)",
                    data=pdf_bytes,
                    file_name=f"rapport_clinique_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )

            except ImportError:
                st.warning("Installez fpdf2 : `pip install fpdf2`")
            except Exception as e:
                st.error(f"Erreur PDF : {e}")
    with tab2:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("🔬 Synthèse Clinique")
            st.info(state.get("diagnostic_summary", "—"))
            st.subheader("💊 Recommandation Intermédiaire")
            st.warning(state.get("interim_care", "—"))
        with c2:
            st.subheader("👨‍⚕️ Traitement Médecin")
            st.success(state.get("physician_treatment", "—"))
            st.subheader("📌 Motif Initial")
            st.markdown(state.get("patient_initial_info", "—"))

    with tab3:
        for i, item in enumerate(state.get("questions_and_answers", []), 1):
            st.markdown(
                f'<div class="qa-q">🩺 <strong>Q{i}: {item["question"]}</strong></div>'
                f'<div class="qa-a">👤 {item["answer"]}</div>',
                unsafe_allow_html=True,
            )

else:
    st.info(f"Synchronisation… (phase: {S['phase']})")
    if S["thread_id"]:
        data = api("get", f"/consultation/{S['thread_id']}")
        sync(data)
    time.sleep(0.5)
    st.rerun()