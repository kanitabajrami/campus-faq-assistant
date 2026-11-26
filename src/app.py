"""Streamlit page for the Campus FAQ Assistant.  Run: streamlit run src/app.py"""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
from assistant import FAQAssistant, KnowledgeBaseError, MAX_LEN  # noqa: E402

st.set_page_config(page_title="Campus FAQ Assistant", page_icon="🎓", layout="wide")


@st.cache_resource
def get_bot(threshold):
    return FAQAssistant(threshold=threshold)


st.title("🎓 Campus FAQ Assistant")
st.caption("ECS-609 prototype · answers come only from the verified FAQ entries · always confirm with the official SEEU office")

with st.sidebar:
    threshold = st.slider("Match threshold (TF-IDF)", 0.0, 1.0, 0.20, 0.05,
                          help="Answers with a similarity score below this value are rejected.")
    st.markdown("**Try an example**")
    examples = ["How do I sign up for courses?", "Where can I check the exam timetable?",
                "My MySEEU account is locked", "What is the best pizza in town?"]
    for ex in examples:
        if st.button(ex, use_container_width=True):
            st.session_state["q"] = ex

try:
    bot = get_bot(threshold)
except KnowledgeBaseError as e:
    st.error(f"The FAQ could not be loaded. {e}")
    st.stop()
st.sidebar.caption(f"FAQ entries loaded: {len(bot.faq)}")

question = st.text_input("Ask a question about the university", key="q", max_chars=None,
                         placeholder="e.g. How can I request a transcript?")
if st.button("Ask", type="primary") or question:
    r = bot.ask(question)
    if r["status"] == "invalid":
        st.warning(r["message"])
    elif r["status"] == "error":
        st.error(r["message"])
    else:
        left, right = st.columns(2)
        t, b = r["tfidf"], r["baseline"]
        with left:
            st.subheader("TF-IDF (AI)")
            if r["status"] == "ok":
                st.success(r["message"])
                st.markdown(f"**Matched FAQ:** {t['entry']['question']}  \n**Score:** {t['score']}  \n"
                            f"**Source:** {t['entry'].get('source_url', '')}  \n**Last verified:** {t['entry'].get('last_verified', '')}")
            else:
                st.info(r["message"])
                st.caption(f"Best score {t['score']} is below the threshold {bot.threshold}.")
        with right:
            st.subheader("Keyword baseline (no AI)")
            if b["accepted"]:
                st.success(b["entry"]["answer"])
                st.markdown(f"**Matched FAQ:** {b['entry']['question']}  \n**Shared words:** {b['overlap']}")
            else:
                st.info("No FAQ shares a content word with your question.")
        with st.expander("Top 3 TF-IDF candidates"):
            for entry, score in t["top3"] or []:
                st.write(f"{entry['faq_id']} · {score} · {entry['question']}")
            if not t["top3"]:
                st.write("No candidate has a score above zero.")
        st.caption(f"Response time: {r['latency_ms']} ms")
    if r.get("log_warning"):
        st.caption("⚠️ " + r["log_warning"])
