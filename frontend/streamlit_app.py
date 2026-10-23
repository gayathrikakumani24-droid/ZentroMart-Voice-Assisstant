"""
ZentroMart VoiceOps — Customer Support Streamlit Web Application.

A clean, retail-support conversational interface powered by FastAPI,
FAISS knowledge retrieval, Groq reasoning, and Gnani.ai voice intelligence.
"""

import os
import base64
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional
import streamlit as st

from frontend.api_client import VoiceOpsClient, VoiceOpsAPIError

# Page Configuration
st.set_page_config(
    page_title="ZentroMart VoiceOps Support",
    page_icon="🛍️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling (Warm off-white background, deep navy, soft mint/sky accents)
st.markdown(
    """
    <style>
    .stApp {
        background-color: #f8fafc;
        color: #0f172a;
    }
    .brand-header {
        font-size: 1.6rem;
        font-weight: 700;
        color: #0f2b46;
        margin-bottom: 0.15rem;
    }
    .brand-subheader {
        font-size: 0.9rem;
        color: #64748b;
        margin-bottom: 1rem;
    }
    .source-badge {
        display: inline-block;
        background-color: #e0f2fe;
        color: #0369a1;
        font-size: 0.75rem;
        font-weight: 600;
        padding: 0.15rem 0.5rem;
        border-radius: 9999px;
        margin-right: 0.35rem;
        margin-bottom: 0.35rem;
        border: 1px solid #bae6fd;
    }
    .ticket-badge {
        display: inline-block;
        background-color: #fef3c7;
        color: #b45309;
        font-weight: 600;
        padding: 0.35rem 0.75rem;
        border-radius: 0.5rem;
        border: 1px solid #fde68a;
        margin-top: 0.5rem;
    }
    .status-pill {
        display: inline-block;
        font-size: 0.8rem;
        padding: 0.2rem 0.6rem;
        border-radius: 1rem;
        font-weight: 600;
    }
    .status-ok { background-color: #d1fae5; color: #065f46; }
    .status-err { background-color: #fee2e2; color: #991b1b; }
    .evidence-item {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        padding: 8px 12px;
        margin-bottom: 8px;
    }
    .evidence-meta {
        font-size: 0.75rem;
        color: #64748b;
        margin-top: 2px;
    }
    .evidence-excerpt {
        font-size: 0.8rem;
        color: #334155;
        border-left: 2px solid #0284c7;
        padding-left: 8px;
        margin-top: 4px;
        font-style: italic;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Initialize API Client
backend_url = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
client = VoiceOpsClient(base_url=backend_url)

# Session State Initialization
if "session_id" not in st.session_state:
    try:
        st.session_state.session_id = client.create_session()
    except Exception:
        st.session_state.session_id = None

if "messages" not in st.session_state:
    st.session_state.messages = []

if "submitted_voice_hashes" not in st.session_state:
    st.session_state.submitted_voice_hashes = set()


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown('<div class="brand-header">🛍️ ZentroMart</div>', unsafe_allow_html=True)
    st.markdown('<div class="brand-subheader">VoiceOps AI Customer Support</div>', unsafe_allow_html=True)
    st.divider()

    # Health Status
    health = client.check_health()
    if health.get("status") == "healthy":
        st.markdown(
            '<span class="status-pill status-ok">● Backend Connected</span>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<span class="status-pill status-err">● Backend Disconnected</span>',
            unsafe_allow_html=True,
        )
        st.caption(f"Target: `{backend_url}`")

    st.divider()

    # Session Info
    st.subheader("Conversation Session")
    if st.session_state.session_id:
        st.code(st.session_state.session_id, language="text")
        turn_count = len([m for m in st.session_state.messages if m["role"] == "user"])
        st.caption(f"Completed Turns: **{turn_count}**")
    else:
        st.warning("No active session.")
        if st.button("Connect New Session"):
            try:
                st.session_state.session_id = client.create_session()
                st.session_state.messages = []
                st.session_state.submitted_voice_hashes.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Could not connect: {e}")

    # New Conversation / Reset
    if st.button("🔄 Start New Conversation", use_container_width=True):
        if st.session_state.session_id:
            try:
                client.reset_session(st.session_state.session_id)
            except Exception:
                pass
        try:
            st.session_state.session_id = client.create_session()
        except Exception:
            pass
        st.session_state.messages = []
        st.session_state.submitted_voice_hashes.clear()
        st.rerun()

    st.divider()
    st.markdown(
        """
        **About ZentroMart Support**  
        • **Strict Grounded Policies**: Answers strictly cite audited returns and refund clauses.  
        • **Zero-Trust Security**: Order tracking is protected by phone suffix/pincode gates.  
        • **Voice Intelligence**: Spoken responses synthesized by Gnani.ai (`Kaveri` voice).  
        """
    )


# ---------------------------------------------------------------------------
# Main Chat Header
# ---------------------------------------------------------------------------
st.markdown("## Customer Support Desk")
st.caption("Ask questions about returns, refunds, order tracking, warranties, or exchanges.")


# ---------------------------------------------------------------------------
# Dedicated Voice Input Section: Talk to ZentroMart
# ---------------------------------------------------------------------------
with st.expander("🎙️ Talk to ZentroMart", expanded=False):
    st.markdown(
        "<small style='color: #64748b;'>Record your inquiry directly with your browser microphone, "
        "or upload an existing audio file.</small>",
        unsafe_allow_html=True,
    )

    tab_mic, tab_upload = st.tabs(["🔴 Live Microphone", "📁 Upload Audio File (Alternative)"])

    # 1. Primary Method: Live Microphone Recording
    with tab_mic:
        st.caption("Click the microphone below, grant browser permission if prompted, and speak.")
        try:
            mic_recording = st.audio_input(
                label="Record voice message",
                key="live_mic_recorder",
                label_visibility="collapsed",
            )
        except Exception as exc:
            st.error(f"Microphone recording unavailable: {exc}")
            mic_recording = None

        if mic_recording is not None:
            mic_bytes = mic_recording.getvalue()
            if len(mic_bytes) > 0:
                mic_hash = hashlib.sha256(mic_bytes).hexdigest()
                mic_already_sent = mic_hash in st.session_state.submitted_voice_hashes

                col_btn, col_info = st.columns([1, 2])
                with col_btn:
                    send_mic = st.button(
                        "📤 Send Voice Message",
                        key="send_live_mic_btn",
                        type="primary",
                        disabled=mic_already_sent,
                        use_container_width=True,
                    )
                with col_info:
                    if mic_already_sent:
                        st.caption("✅ *This recording has already been submitted.*")
                    else:
                        st.caption(f"Ready to send ({round(len(mic_bytes) / 1024, 1)} KB audio)")

                if send_mic and not mic_already_sent:
                    st.session_state.submitted_voice_hashes.add(mic_hash)
                    with st.spinner("Transcribing with Gnani STT & generating response..."):
                        try:
                            if not st.session_state.session_id:
                                st.session_state.session_id = client.create_session()

                            v_res = client.upload_voice_message(
                                audio_bytes=mic_bytes,
                                filename=f"live_recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav",
                                session_id=st.session_state.session_id,
                                content_type="audio/wav",
                            )

                            transcript = (v_res.get("transcript") or "").strip()
                            answer = v_res.get("answer", "")
                            sources = v_res.get("sources", [])
                            evidence = v_res.get("evidence", [])
                            audio_b64 = v_res.get("audio_base64")
                            tts_ok = v_res.get("tts_generated", False)
                            tts_err = v_res.get("error")

                            # Add user message
                            st.session_state.messages.append({
                                "role": "user",
                                "content": transcript if transcript else "(Voice message)",
                                "audio_label": "Live Microphone Recording",
                                "timestamp": datetime.now().strftime("%H:%M"),
                            })

                            # Add assistant response
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": answer,
                                "sources": sources,
                                "evidence": evidence,
                                "audio_base64": audio_b64,
                                "tts_generated": tts_ok,
                                "tts_error": tts_err,
                                "is_voice": True,
                                "timestamp": datetime.now().strftime("%H:%M"),
                            })
                            st.rerun()

                        except VoiceOpsAPIError as exc:
                            st.session_state.submitted_voice_hashes.discard(mic_hash)
                            st.error(f"Voice Processing Error: {exc}")
                        except Exception as exc:
                            st.session_state.submitted_voice_hashes.discard(mic_hash)
                            st.error(f"Connection Error: {exc}")
            else:
                st.warning("Recording is empty (0 bytes). Please speak clearly into your microphone.")

    # 2. Secondary Method: Audio File Upload
    with tab_upload:
        st.caption("Alternative: Upload an audio recording supported by Gnani STT (.wav, .mp3, .ogg, .flac, .aac, .m4a).")
        uploaded_file = st.file_uploader(
            "Upload audio file",
            type=["wav", "mp3", "ogg", "flac", "aac", "m4a"],
            key="voice_file_uploader",
            label_visibility="collapsed",
            help="Alternative to recording live with your microphone.",
        )
        if uploaded_file is not None:
            file_bytes = uploaded_file.getvalue()
            if len(file_bytes) > 0:
                file_hash = hashlib.sha256(file_bytes).hexdigest()
                file_already_sent = file_hash in st.session_state.submitted_voice_hashes

                # Playback preview
                st.audio(file_bytes, format=uploaded_file.type or "audio/wav")

                col_f_btn, col_f_info = st.columns([1, 2])
                with col_f_btn:
                    send_file = st.button(
                        "📤 Send Uploaded Audio",
                        key="send_uploaded_file_btn",
                        type="primary",
                        disabled=file_already_sent,
                        use_container_width=True,
                    )
                with col_f_info:
                    if file_already_sent:
                        st.caption("✅ *This audio file has already been submitted.*")
                    else:
                        st.caption(f"`{uploaded_file.name}` ({round(len(file_bytes) / 1024, 1)} KB)")

                if send_file and not file_already_sent:
                    st.session_state.submitted_voice_hashes.add(file_hash)
                    with st.spinner("Transcribing with Gnani STT & generating response..."):
                        try:
                            if not st.session_state.session_id:
                                st.session_state.session_id = client.create_session()

                            v_res = client.upload_voice_message(
                                audio_bytes=file_bytes,
                                filename=uploaded_file.name,
                                session_id=st.session_state.session_id,
                                content_type=uploaded_file.type or "audio/wav",
                            )

                            transcript = (v_res.get("transcript") or "").strip()
                            answer = v_res.get("answer", "")
                            sources = v_res.get("sources", [])
                            evidence = v_res.get("evidence", [])
                            audio_b64 = v_res.get("audio_base64")
                            tts_ok = v_res.get("tts_generated", False)
                            tts_err = v_res.get("error")

                            # Add user message
                            st.session_state.messages.append({
                                "role": "user",
                                "content": transcript if transcript else "(Uploaded audio)",
                                "audio_label": uploaded_file.name,
                                "timestamp": datetime.now().strftime("%H:%M"),
                            })

                            # Add assistant response
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": answer,
                                "sources": sources,
                                "evidence": evidence,
                                "audio_base64": audio_b64,
                                "tts_generated": tts_ok,
                                "tts_error": tts_err,
                                "is_voice": True,
                                "timestamp": datetime.now().strftime("%H:%M"),
                            })
                            st.rerun()

                        except VoiceOpsAPIError as exc:
                            st.session_state.submitted_voice_hashes.discard(file_hash)
                            st.error(f"Voice Processing Error: {exc}")
                        except Exception as exc:
                            st.session_state.submitted_voice_hashes.discard(file_hash)
                            st.error(f"Connection Error: {exc}")
            else:
                st.warning("Uploaded file is empty (0 bytes).")


# ---------------------------------------------------------------------------
# Welcome Banner & Suggested Questions (when conversation is empty)
# ---------------------------------------------------------------------------
if not st.session_state.messages:
    with st.chat_message("assistant", avatar="🛍️"):
        st.markdown(
            "Hello! I am your **ZentroMart Customer Support Assistant**. "
            "How can I assist you with your orders, returns, or policies today?"
        )

    st.markdown("**Suggested questions to get started:**")
    cols = st.columns(2)
    suggested = [
        "How long does a wallet refund take?",
        "What is the return policy for clothing?",
        "How do I claim a product warranty?",
        "I need help tracking my order.",
    ]
    for idx, prompt_text in enumerate(suggested):
        col = cols[idx % 2]
        if col.button(prompt_text, key=f"sugg_{idx}", use_container_width=True):
            st.session_state.pending_query = prompt_text
            st.rerun()

# Check for pending suggested query
if "pending_query" in st.session_state:
    user_query = st.session_state.pop("pending_query")
    st.session_state.messages.append({
        "role": "user",
        "content": user_query,
        "timestamp": datetime.now().strftime("%H:%M"),
    })

    with st.spinner("Retrieving verified policies..."):
        try:
            res = client.send_chat_message(user_query, session_id=st.session_state.session_id)
            st.session_state.messages.append({
                "role": "assistant",
                "content": res.get("answer", ""),
                "sources": res.get("sources", []),
                "evidence": res.get("evidence", []),
                "ticket_created": res.get("ticket_created", False),
                "ticket_id": res.get("ticket_id"),
                "timestamp": datetime.now().strftime("%H:%M"),
            })
        except VoiceOpsAPIError as exc:
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"⚠️ **Error**: {exc}",
                "timestamp": datetime.now().strftime("%H:%M"),
            })
    st.rerun()


# ---------------------------------------------------------------------------
# Conversation History: Customer and Assistant Messages
# ---------------------------------------------------------------------------
for msg in st.session_state.messages:
    if msg["role"] == "user":
        with st.chat_message("user"):
            st.markdown(msg["content"])
            if msg.get("audio_label"):
                st.caption(f"🎙️ *Voice Inquiry:* `{msg['audio_label']}`")
    else:
        with st.chat_message("assistant", avatar="🛍️"):
            st.markdown(msg["content"])

            # Spoken Voice Playback if generated
            if msg.get("audio_base64"):
                audio_bytes = base64.b64decode(msg["audio_base64"])
                st.audio(audio_bytes, format="audio/wav")
            elif msg.get("is_voice") and not msg.get("tts_generated"):
                st.caption("ℹ️ *Spoken audio playback is temporarily unavailable.*")

            # Ticket escalation notice
            if msg.get("ticket_created") and msg.get("ticket_id"):
                st.markdown(
                    f'<div class="ticket-badge">🎫 Escalation Ticket Created: <b>{msg["ticket_id"]}</b></div>',
                    unsafe_allow_html=True,
                )

            # Compact, Collapsible Supporting Policy Evidence Expander
            sources = msg.get("sources") or []
            evidence = msg.get("evidence") or []
            if sources or evidence:
                with st.expander("Supporting Policy Evidence", expanded=False):
                    if sources:
                        st.markdown("**Cited Policy Sections:**")
                        badges_html = " ".join([f'<span class="source-badge">[{s}]</span>' for s in sources])
                        st.markdown(badges_html, unsafe_allow_html=True)

                    if evidence:
                        st.markdown("**Grounding Evidence Details:**")
                        for ev in evidence:
                            sec_id = ev.get("section_id") or "Policy"
                            doc_name = ev.get("source") or "Policy Document"
                            heading = ev.get("heading") or ""
                            eff_date = ev.get("effective_from")
                            excerpt = ev.get("excerpt")

                            meta_parts = [f"**Doc:** `{doc_name}`"]
                            if eff_date:
                                meta_parts.append(f"**Effective:** `{eff_date}`")
                            meta_line = " | ".join(meta_parts)

                            st.markdown(f"- <span class=\"source-badge\">[{sec_id}]</span> **{heading}**", unsafe_allow_html=True)
                            st.markdown(f"  <small style='color: #64748b;'>{meta_line}</small>", unsafe_allow_html=True)
                            if excerpt:
                                clean_excerpt = excerpt.strip().replace("\n", " ")
                                if len(clean_excerpt) > 280:
                                    clean_excerpt = clean_excerpt[:280] + "..."
                                st.markdown(f"  > *\"{clean_excerpt}\"*")


# ---------------------------------------------------------------------------
# Text Chat Input
# ---------------------------------------------------------------------------
prompt = st.chat_input("Type your question here (e.g., 'What is the return window for clothing?')...")
if prompt:
    # Append user message
    st.session_state.messages.append({
        "role": "user",
        "content": prompt,
        "timestamp": datetime.now().strftime("%H:%M"),
    })

    # Call FastAPI backend
    with st.spinner("Consulting ZentroMart policies..."):
        try:
            if not st.session_state.session_id:
                st.session_state.session_id = client.create_session()

            res = client.send_chat_message(prompt, session_id=st.session_state.session_id)
            st.session_state.messages.append({
                "role": "assistant",
                "content": res.get("answer", ""),
                "sources": res.get("sources", []),
                "evidence": res.get("evidence", []),
                "ticket_created": res.get("ticket_created", False),
                "ticket_id": res.get("ticket_id"),
                "timestamp": datetime.now().strftime("%H:%M"),
            })
        except VoiceOpsAPIError as exc:
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"⚠️ **Connection Error**: {exc}",
                "timestamp": datetime.now().strftime("%H:%M"),
            })
    st.rerun()
