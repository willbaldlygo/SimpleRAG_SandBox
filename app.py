import os
import io
import re
import json
from typing import List, Dict, Optional, Tuple

import streamlit as st
import requests
from dotenv import load_dotenv
from pypdf import PdfReader
try:
    from docx import Document as DocxDocument
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False


# --- Setup ---
load_dotenv()

APP_TITLE = "Digital Peninsula: ChatBot Sandbox"


# --- Utilities ---
def ensure_session_state():
    if "messages" not in st.session_state:
        st.session_state["messages"] = []  # list of {role, content}
    if "system_prompt" not in st.session_state:
        # Initialize with example prompt; users can edit/delete freely
        st.session_state["system_prompt"] = load_example_system_prompt()
    if "raw_request" not in st.session_state:
        st.session_state["raw_request"] = None
    if "kb" not in st.session_state:
        st.session_state["kb"] = None  # dict with {text, chunks, pages, filename}
    if "model_provider" not in st.session_state:
        st.session_state["model_provider"] = "Cloudflare"  # Default to Cloudflare (tiny/naive model)


def load_example_system_prompt() -> str:
    return (
        "You are a helpful AI assistant. Your job is to answer questions for your user. "
        "Keep your tone friendly, but professional."
    )


# --- Knowledge base helpers ---
WORD_RE = re.compile(r"[A-Za-z0-9']+")
STOPWORDS = set(
    """
    a an and are as at be but by for from has have how i if in into is it its of on or that the their them then there these they this to was we what when where which who why will with you your yours our ours us
    """.split()
)


def extract_pdf_text(file_bytes: bytes) -> Tuple[str, int]:
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        pages = len(reader.pages)
        texts = []
        for p in reader.pages:
            try:
                txt = p.extract_text() or ""
            except Exception:
                txt = ""
            texts.append(txt)
        full = "\n\n".join(texts)
        return full, pages
    except Exception:
        return "", 0


def extract_text_file(file_bytes: bytes) -> Tuple[str, int]:
    """Extract text from .txt or .md files."""
    try:
        text = file_bytes.decode("utf-8")
        # Estimate "pages" as ~3000 chars per page
        pages = max(1, len(text) // 3000)
        return text, pages
    except Exception:
        return "", 0


def extract_docx_text(file_bytes: bytes) -> Tuple[str, int]:
    """Extract text from .docx files."""
    if not DOCX_AVAILABLE:
        return "", 0
    try:
        doc = DocxDocument(io.BytesIO(file_bytes))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        text = "\n\n".join(paragraphs)
        # Estimate pages
        pages = max(1, len(text) // 3000)
        return text, pages
    except Exception:
        return "", 0


def extract_file_text(file_bytes: bytes, filename: str) -> Tuple[str, int]:
    """Route to appropriate extractor based on file extension."""
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext == "pdf":
        return extract_pdf_text(file_bytes)
    elif ext in ("txt", "md"):
        return extract_text_file(file_bytes)
    elif ext == "docx":
        return extract_docx_text(file_bytes)
    else:
        return "", 0


def _tokenize(text: str) -> List[str]:
    return [t.lower() for t in WORD_RE.findall(text)]


def chunk_text(text: str, max_words: int = 220) -> List[str]:
    # Split by paragraphs first
    paras = [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]
    chunks: List[str] = []
    for para in paras:
        tokens = _tokenize(para)
        if not tokens:
            continue
        # Slide over long paragraphs
        start = 0
        while start < len(tokens):
            end = min(start + max_words, len(tokens))
            piece_tokens = tokens[start:end]
        # Reconstruct approximate text piece
            piece = " ".join(piece_tokens)
            chunks.append(piece)
            start = end
    # Fallback if nothing
    if not chunks and text.strip():
        tokens = _tokenize(text)
        for i in range(0, len(tokens), max_words):
            chunks.append(" ".join(tokens[i:i + max_words]))
    return chunks


def score_chunk(query_tokens: List[str], chunk_tokens: List[str]) -> float:
    # Simple overlap score with slight length penalty
    if not chunk_tokens:
        return 0.0
    q_set = [t for t in query_tokens if t not in STOPWORDS]
    if not q_set:
        q_set = query_tokens
    counts = {}
    for t in chunk_tokens:
        counts[t] = counts.get(t, 0) + 1
    score = sum(counts.get(t, 0) for t in set(q_set))
    penalty = 1.0 + len(chunk_tokens) / 400.0
    return score / penalty


def retrieve_relevant_chunks(query: str, chunks: List[str], k: int = 3) -> List[str]:
    if not chunks:
        return []
    q_tokens = _tokenize(query)
    scored = []
    for ch in chunks:
        ch_tokens = _tokenize(ch)
        s = score_chunk(q_tokens, ch_tokens)
        if s > 0:
            scored.append((s, ch))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:k]]


# --- Model calls ---
def call_groq(messages: List[Dict[str, str]], model: str = "openai/gpt-oss-20b") -> Tuple[Optional[str], Optional[str]]:
    """Call Groq API for fast inference.

    Returns (assistant_text, error_message). One will be None.
    Also stores raw request payload in session_state for debugging.
    """
    api_key = os.getenv("GROQ_API_KEY") or st.secrets.get("GROQ_API_KEY", None)
    if not api_key:
        return None, "Missing GROQ_API_KEY. Get a free key at https://console.groq.com"

    # Groq Chat Completions API endpoint
    groq_url = "https://api.groq.com/openai/v1/chat/completions"

    # Prepare raw payload for display
    raw_payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 512,
    }
    st.session_state["raw_request"] = {"provider": "groq", "payload": raw_payload, "model": model}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(groq_url, headers=headers, json=raw_payload, timeout=30)
        response.raise_for_status()
        result = response.json()

        text = result.get("choices", [{}])[0].get("message", {}).get("content", "")

        if not text or not text.strip():
            return None, "Empty response from Groq."
        return text.strip(), None
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 429:
            return None, "Groq is rate-limited right now — wait a few seconds and try again."
        return None, f"Groq API error: {e} - {e.response.text if hasattr(e, 'response') else ''}"
    except requests.exceptions.Timeout:
        return None, "Groq request timed out."
    except Exception as e:
        return None, f"Groq error: {e}"


def call_cloudflare(messages: List[Dict[str, str]], model: str = "@cf/meta/llama-3.2-1b-instruct") -> Tuple[Optional[str], Optional[str]]:
    """Call Cloudflare Workers AI for fast inference with a tiny, unaligned model.

    Returns (assistant_text, error_message). One will be None.
    Also stores raw request payload in session_state for debugging.
    """
    api_token = os.getenv("CLOUDFLARE_API_TOKEN") or st.secrets.get("CLOUDFLARE_API_TOKEN", None)
    account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID") or st.secrets.get("CLOUDFLARE_ACCOUNT_ID", None)
    if not api_token or not account_id:
        return None, "Missing CLOUDFLARE_API_TOKEN or CLOUDFLARE_ACCOUNT_ID. Get a free account at https://dash.cloudflare.com"

    # Cloudflare Workers AI OpenAI-compatible Chat Completions endpoint
    cloudflare_url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1/chat/completions"

    # Prepare raw payload for display
    raw_payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 512,
    }
    st.session_state["raw_request"] = {"provider": "cloudflare", "payload": raw_payload, "model": model}

    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(cloudflare_url, headers=headers, json=raw_payload, timeout=30)
        response.raise_for_status()
        result = response.json()

        text = result.get("choices", [{}])[0].get("message", {}).get("content", "")

        if not text or not text.strip():
            return None, "Empty response from Cloudflare."
        return text.strip(), None
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 429:
            return None, "Cloudflare's free daily quota may be used up — try again later, or switch to the Groq model."
        return None, f"Cloudflare API error: {e} - {e.response.text if hasattr(e, 'response') else ''}"
    except requests.exceptions.Timeout:
        return None, "Cloudflare request timed out."
    except Exception as e:
        return None, f"Cloudflare error: {e}"


# --- UI ---
def sidebar():
    with st.sidebar:
        st.header("Settings")

        # Model provider selection
        st.subheader("Model Selection")
        provider = st.selectbox(
            "Choose Model",
            ["Cloudflare (Llama 3.2 1B)", "Groq (gpt-oss-20b)"],
            index=0 if st.session_state.get("model_provider", "Cloudflare") == "Cloudflare" else 1
        )
        # Update session state based on selection
        if "Cloudflare" in provider:
            st.session_state["model_provider"] = "Cloudflare"
        else:
            st.session_state["model_provider"] = "Groq"

        # System prompt editor
        st.subheader("System Prompt")
        st.session_state["system_prompt"] = st.text_area(
            "Edit the system prompt",
            value=st.session_state.get("system_prompt", ""),
            height=180,
        )

        # Buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Reset Conversation", use_container_width=True):
                st.session_state["messages"] = []
        with col2:
            if st.button("Reset Prompt", use_container_width=True):
                st.session_state["system_prompt"] = load_example_system_prompt()

        # API key / service status
        st.subheader("Service Status")
        cloudflare_ok = bool(
            (os.getenv("CLOUDFLARE_API_TOKEN") or st.secrets.get("CLOUDFLARE_API_TOKEN", None))
            and (os.getenv("CLOUDFLARE_ACCOUNT_ID") or st.secrets.get("CLOUDFLARE_ACCOUNT_ID", None))
        )
        st.caption(f"Cloudflare API: {'✅ set' if cloudflare_ok else '⚠️ missing'}")

        # Check Groq API key
        groq_ok = bool(os.getenv("GROQ_API_KEY") or st.secrets.get("GROQ_API_KEY", None))
        st.caption(f"Groq API: {'✅ set' if groq_ok else '⚠️ missing'}")

        # Knowledge base uploader
        with st.expander("Knowledge Base", expanded=False):
            kb = st.session_state.get("kb")
            uploaded = st.file_uploader(
                "Upload a document", 
                type=["pdf", "txt", "md", "docx"], 
                accept_multiple_files=False,
                help="Supported: PDF, TXT, MD, DOCX"
            )
            
            if st.button("Clear KB", use_container_width=True):
                st.session_state["kb"] = None

            if uploaded:
                with st.spinner("Extracting text…"):
                    content, pages = extract_file_text(uploaded.read(), uploaded.name)
                if not content.strip():
                    st.warning("Could not extract text from the file.")
                else:
                    chunks = chunk_text(content)
                    st.session_state["kb"] = {
                        "filename": uploaded.name,
                        "pages": pages,
                        "text": content,
                        "chunks": chunks,
                        "n_chunks": len(chunks),
                    }

            kb = st.session_state.get("kb")
            if kb:
                st.success(f"Loaded {kb['filename']} — {kb['pages']} pages, {kb['n_chunks']} chunks")
                st.caption("The most relevant excerpts will be provided to the model with your question.")
            else:
                st.info("No knowledge base loaded.")


def render_chat():
    # Render prior messages
    for msg in st.session_state["messages"]:
        role = msg.get("role", "assistant")
        content = msg.get("content", "")
        if hasattr(st, "chat_message"):
            with st.chat_message(role):
                st.markdown(content)
        else:
            # Fallback render
            st.markdown(f"**{role.title()}:** {content}")


def main():
    st.set_page_config(page_title=APP_TITLE, page_icon="💬")
    ensure_session_state()

    st.title(APP_TITLE)
    sidebar()

    render_chat()

    # Chat input
    user_input = st.chat_input("Type your message…") if hasattr(st, "chat_input") else st.text_input("Your message")

    # Handle sending
    if user_input:
        # Append user message to history
        st.session_state["messages"].append({"role": "user", "content": user_input})

        # Prepare request
        base_system_prompt = st.session_state["system_prompt"] or ""

        # RAG: build contextual system prompt using KB
        effective_system_prompt = base_system_prompt
        kb = st.session_state.get("kb")
        if kb and kb.get("chunks"):
            top_chunks = retrieve_relevant_chunks(user_input, kb["chunks"], k=3)
            if top_chunks:
                context = "\n\n".join(f"- {c}" for c in top_chunks)
                effective_system_prompt = (
                    f"{base_system_prompt}\n\n"
                    "Use the following knowledge base excerpts if relevant. "
                    "If the KB does not contain the answer, say so or ask for clarification.\n"
                    "[Knowledge Base Excerpts]\n"
                    f"{context}"
                )

        # Build API-compatible messages
        api_messages = [{"role": "system", "content": effective_system_prompt}] + st.session_state["messages"]

        # Call the selected model
        provider = st.session_state.get("model_provider", "Cloudflare")
        if provider == "Groq":
            with st.spinner("Calling Groq (gpt-oss-20b)…"):
                assistant_text, error = call_groq(api_messages, model="openai/gpt-oss-20b")
        else:
            with st.spinner("Calling Cloudflare (Llama 3.2 1B)…"):
                assistant_text, error = call_cloudflare(api_messages)

        # Store the error or response in session state so it persists after rerun
        if error:
            st.session_state["last_error"] = error
            st.session_state["messages"].append({"role": "assistant", "content": f"❌ Error: {error}"})
        elif assistant_text:
            st.session_state["last_error"] = None
            st.session_state["messages"].append({"role": "assistant", "content": assistant_text})
        else:
            st.session_state["last_error"] = "No response received"
            st.session_state["messages"].append({"role": "assistant", "content": "❌ No response received from the API. Please check your API key and try again."})

        # Re-render updated conversation
        if hasattr(st, "rerun"):
            st.rerun()
        else:
            st.experimental_rerun()

    # Raw request viewer
    with st.expander("Show raw request"):
        raw = st.session_state.get("raw_request")
        if not raw:
            st.info("No request sent yet.")
        else:
            provider_name = raw.get("provider", "unknown").title()
            st.caption(f"{provider_name} API payload")
            st.json(raw.get("payload"))


if __name__ == "__main__":
    main()
