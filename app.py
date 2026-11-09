"""Streamlit entry point for Ask Bayley."""

import os
from urllib.error import URLError

import streamlit as st

from bayley import draft_answer, find_entries, load_data

st.set_page_config(page_title="Ask Bayley", page_icon="🦅")
st.title("Ask Bayley")
st.caption("An SFBU student guide for deadlines, policies, and campus support")
st.info("Hackathon prototype · Summer 2027 standard semester and selected support contacts")

sources, entries = load_data()
live = bool(os.environ.get("BAYLEY_WEBUI_API_KEY"))
with st.sidebar:
    st.subheader("SFBU sources")
    for source in sources.values():
        st.markdown(f"[{source['title']}]({source['url']})")
    st.caption("DGX drafting enabled" if live else "Local preview · curated source notes")

term = st.selectbox("Academic term", ["Choose a term", "Summer 2027"])
st.caption("Try “What is the add/drop deadline?” or “Where do I get Canvas help?”")
question = st.text_input("Your question", max_chars=500)

if st.button("Find guidance", type="primary") and question.strip():
    matches = find_entries(question, term, entries)
    if not matches:
        st.info("The current source set has no matching entry. Check the SFBU sources in the sidebar.")
    else:
        if live:
            with st.spinner("Drafting from the source notes on the DGX…"):
                try:
                    answer = draft_answer(question, matches)
                except (URLError, TimeoutError, ValueError, KeyError, IndexError, TypeError):
                    st.info("The model draft is unavailable. The source notes are below.")
                else:
                    st.subheader("Model draft")
                    st.write(answer)
        st.subheader("Matching source notes")
        for entry in matches:
            st.markdown(f"**{entry['title']}**")
            st.write(entry["text"])
            st.caption(entry["section"])
            links = [
                f"[{sources[source_id]['title']}]({sources[source_id]['url']})"
                for source_id in entry["source_ids"]
            ]
            st.markdown(" · ".join(links))
