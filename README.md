# Digital Peninsula: ChatBot Sandbox

A simple, lightweight RAG based ChatBot with an exposed system prompt. Designed to help my AI Bootcamp learners understand how their system prompts effect the behaviour of ChatBots built on smaller, local LLM models.

- Groq Chat Completions (`openai/gpt-oss-20b`)
- Cloudflare Workers AI (`@cf/meta/llama-3.2-1b-instruct`)

The app provides a sidebar for model selection, a live-editable system prompt, reset and example buttons, chat history rendering, and a raw request viewer.

## Quick Start
1) Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
```

2) Install dependencies

```bash
pip install -r requirements.txt
```

3) Set environment variables

Copy `.env.example` to `.env` and add your keys, or export them directly in your shell.

```bash
cp .env.example .env
# Then edit .env to add your keys
# GROQ_API_KEY=...
# CLOUDFLARE_API_TOKEN=...
# CLOUDFLARE_ACCOUNT_ID=...
```

Alternatively, export in your shell session:

```bash
export GROQ_API_KEY=your_groq_key
export CLOUDFLARE_API_TOKEN=your_cloudflare_api_token
export CLOUDFLARE_ACCOUNT_ID=your_cloudflare_account_id
```

4) Run the app

```bash
streamlit run app.py
```

Open the URL shown in the terminal (usually http://localhost:8501).

## Features

- Sidebar controls:
  - Model selector: `Cloudflare: @cf/meta/llama-3.2-1b-instruct` (default) or `Groq: openai/gpt-oss-20b`
  - Editable System Prompt text area
  - Reset Conversation (clears history, keeps system prompt)
  - Load Example Prompt (friendly, professional helper template). The example prompt is pre-filled by default on first launch; you can edit or clear it anytime.
- Main area:
  - Chat history rendered using `st.chat_message`
  - `st.chat_input` for live input
  - "Show raw request" expander displaying the exact payload (Cloudflare or Groq)
  - Knowledge Base: Upload a document (PDF, TXT, MD, DOCX) in the sidebar. The app extracts text, chunks it, and retrieves top matching excerpts for each question, augmenting the system prompt. Use "Clear KB" to remove it.

## Pushing to GitHub

Initialize a repo and push to GitHub:

```bash
git init
git add .
git commit -m "Add Digital Peninsula: ChatBot Sandbox"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

## Deploying on Hugging Face Spaces

1) Create a new Space (Streamlit) and push your repo files there.
2) In the Space Settings, add the following Secrets:
   - `GROQ_API_KEY` (for Groq backend)
   - `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` (for Cloudflare Workers AI backend)
3) The app reads these from the environment automatically.

Notes:
- Errors and missing keys are surfaced in-app via warnings/errors.

## Project Structure

```
.
├── app.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```
