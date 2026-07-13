# Model Provider Setup

This app uses two free, no-credit-card-required backends: Groq (fast, competent small model) and Cloudflare Workers AI (a genuinely tiny, more naive model). Both are configured with environment variables / Streamlit secrets.

## Groq

- **Free tier**: 30 requests/minute, 14,400 requests/day (shared across the whole app)
- **Extremely fast**: sub-second response times
- **Model**: `openai/gpt-oss-20b` — a small but modern, well-aligned model

### Getting a free Groq API key

1. **Sign up for a free Groq account**
   - Go to https://console.groq.com
   - Click "Sign Up" and create a free account

2. **Generate an API key**
   - After logging in, go to https://console.groq.com/keys
   - Click "Create API Key"
   - Give it a name (e.g., "chatbot-app")
   - Copy your API key (starts with `gsk_...`)

3. **Add the key to your app**
   - **For local development**:
     - Create a `.env` file in this directory (copy from `.env.example`)
     - Add the line: `GROQ_API_KEY=gsk_your_key_here`
   - **For Streamlit Cloud**:
     - Go to your app settings on Streamlit Cloud
     - Find the "Secrets" section
     - Add: `GROQ_API_KEY = "gsk_your_key_here"`

Note: Groq's 30 requests/minute limit is shared across the whole class. With a full room of learners, it's possible to hit this cap if many people send a message in the same minute — the app will show a "rate-limited, try again" message rather than a raw error in that case.

## Cloudflare Workers AI

- **Free tier**: 10,000 Neurons/day (resets daily), metered by usage rather than a per-minute request cap — better suited to a full classroom sending messages around the same time
- **No credit card required**
- **Model**: `@cf/meta/llama-3.2-1b-instruct` — a genuinely small (1B parameter), lightly-aligned model that still attempts to answer things it doesn't know, making it useful for demonstrating the limits of small/isolated LLMs

### Getting free Cloudflare credentials

1. **Sign up for a free Cloudflare account**
   - Go to https://dash.cloudflare.com/sign-up

2. **Find your Account ID**
   - In the Cloudflare dashboard, select your account
   - Your Account ID is shown on the right-hand sidebar of the Workers & Pages overview page

3. **Create a Workers AI API token**
   - Go to https://dash.cloudflare.com/profile/api-tokens
   - Click "Create Token" and use (or start from) the "Workers AI" template, or grant `Account.Workers AI: Read` permission
   - Copy the generated token

4. **Add the credentials to your app**
   - **For local development**:
     - Add to your `.env` file: `CLOUDFLARE_API_TOKEN=your_token_here` and `CLOUDFLARE_ACCOUNT_ID=your_account_id_here`
   - **For Streamlit Cloud**:
     - Add both `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` to the app's Secrets

## Deploying to Streamlit Cloud

When deploying, add all three secrets in the app's Settings → Secrets:

```toml
GROQ_API_KEY = "gsk_your_key_here"
CLOUDFLARE_API_TOKEN = "your_cloudflare_api_token"
CLOUDFLARE_ACCOUNT_ID = "your_cloudflare_account_id"
```

Save and the app will automatically restart.
