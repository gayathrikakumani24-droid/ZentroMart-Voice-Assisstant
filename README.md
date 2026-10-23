# ZentroMart VoiceOps — Customer Support Agent & Web Application

ZentroMart VoiceOps is an enterprise-grade, voice- and text-enabled AI customer support agent tailored for e-commerce operations. It handles customer inquiries spanning policy questions, returns and exchanges, order status lookups, and dispute escalations under strict identity verification gates, business-day calendar rules, and grounded retrieval constraints.

The system features a **FastAPI REST API backend** and a modern **React + Vite web application** (with Midnight Navy + Mint Teal design system, live browser microphone recording, and collapsible policy evidence), alongside the legacy Streamlit frontend, batch audio runners, and interactive CLI interfaces.

---

## 1. Project Purpose & Problem Statement

Modern e-commerce customer support faces high call volumes, complex multi-version return policies, and strict compliance requirements around customer data protection. Customers frequently inquire in natural spoken language (including Indian English and Hinglish phrases) regarding refunds, return windows, delivery delays, and high-value package damage.

ZentroMart VoiceOps solves these challenges by providing:
1. **Accurate Voice Interaction**: Spoken customer queries are transcribed via speech-to-text (STT) and responses are delivered via text-to-speech (TTS) powered by Gnani.ai. Live browser microphone recording encodes clean 16kHz mono PCM WAV audio directly in the client.
2. **Strict Groundedness**: Every policy answer cites verified knowledge base sections (`[RET-1]`, `[PAY-3]`, etc.) and avoids hallucinating unsupported claims.
3. **Identity-Gated Tool Security**: Customer order details are never disclosed without verifying identity (last 4 digits of registered phone number or 6-digit delivery pincode).
4. **Calendar-Aware Business Logic**: Return windows and refund processing timelines accurately compute business days (Monday–Saturday) while respecting Indian national holidays.
5. **Modern React + Vite Frontend**: Responsive web app built with React, Vite, and custom CSS variables implementing the Midnight Navy (`#14243A`) and Mint Teal (`#0F766E`) design system.
6. **Collapsible Supporting Policy Evidence**: Per-message expandable policy sources with excerpts, section IDs, effective dates, and policy status.
7. **Deterministic Audit Evidence**: Every voice and text interaction outputs structured JSON evidence recording sources, decisions, and tool executions.

---

## 2. System Architecture & VoiceOps Pipeline

```
  ┌────────────────────────────────────────────────────────┐
  │         React + Vite Web App (Browser UI)              │
  │     (frontend/src/App.jsx + useConversation hook)      │
  │     * Legacy Streamlit UI available as fallback        │
  └───────────────────────────┬────────────────────────────┘
                              │ HTTP Requests (CORS enabled)
                              ▼
  ┌────────────────────────────────────────────────────────┐
  │             FastAPI Backend (api/main.py)              │
  │    (Endpoints: /health, /sessions, /chat, /voice)      │
  └───────┬────────────────────────────────────────┬───────┘
          │                                        │
          ▼                                        ▼
┌──────────────────────┐              ┌───────────────────────────┐
│      Gnani STT       │              │      Gnani TTS            │
│ (gnani-vachana en-IN)│              │ (voice: Kaveri,           │
└─────────┬────────────┘              │  model: timbre-v2.5)      │
          │ Transcribed Text          └─────────────▲─────────────┘
          ▼                                         │
┌──────────────────────┐                            │
│ Conversation Manager │                            │
│ (Isolated sessions,  │                            │
│  history, entities)  │                            │
└─────────┬────────────┘                            │
          │                                         │
    ┌─────┴─────────────────────────┐               │
    ▼                               ▼               │
┌───────────────────────┐   ┌───────────────────┐   │
│   FAISS RAG Engine    │   │ Secure Tool &     │   │
│ (21 Markdown docs,    │   │ Business Date     │   │
│  versioning, vectors) │   │ (lookup, ticket)  │   │
└──────────┬────────────┘   └─────────┬─────────┘   │
           │                          │             │
           └────────────┬─────────────┘             │
                        │ Evidence & Context        │
                        ▼                           │
          ┌───────────────────────────┐             │
          │    Groq LLaMA / OSS LLM   │─────────────┘
          │   (Grounded Synthesis)    │ Spoken Answer
          └───────────────────────────┘
```

---

## 3. Technology Stack & Key Dependencies

- **Backend Framework**: `fastapi>=0.110.0`, `uvicorn>=0.28.0`
- **Frontend Framework**: `streamlit>=1.35.0`
- **Voice STT**: `gnani-vachana` SDK (v0.8.2) — `gnani.stt.GnaniSTTClient`, language `en-IN`.
- **Voice TTS**: `gnani-vachana` SDK (v0.8.2) — `gnani.tts.GnaniTTSClient`, voice `Kaveri`, model `timbre-v2.5`, language `en-IN`.
- **LLM Reasoning**: `groq` SDK with offline grounded fallback.
- **Vector Search / RAG**: `faiss-cpu` (v1.8.0+), `sentence-transformers` (`all-MiniLM-L6-v2`), cosine similarity retrieval.
- **Data Validation & Business Rules**: Python standard library (`csv`, `json`, `datetime`, `unittest`).

---

## 4. Environment Setup & Installation

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Configure Environment Variables
Copy `.env.example` to create a local `.env`:
```bash
cp .env.example .env
```
Populate `.env` with your API credentials and configuration:
```env
# Groq LLM Configuration
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-120b

# Gnani.ai Voice Configuration (STT & TTS REST API Key)
GNANI_API_KEY=your_gnani_api_key_here

# Frontend / API Server Configuration
BACKEND_URL=http://127.0.0.1:8000
```
> **Security Notice**: `.env` is ignored by Git in `.gitignore`. Never commit API keys or secret tokens.

---

## 5. Running the Web Application

To run the complete web application, start the FastAPI backend and the React frontend in separate terminals:

### Terminal 1: Start the FastAPI Backend
```powershell
python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```
- **Backend API**: `http://127.0.0.1:8000`
- **Interactive Swagger Documentation**: `http://127.0.0.1:8000/docs`
- **OpenAPI JSON Schema**: `http://127.0.0.1:8000/openapi.json`

### Terminal 2: Start the React + Vite Frontend (Primary)
```powershell
cd frontend
npm install
npm run dev
```
- **Web App Interface**: Opens at `http://localhost:5173`.
- **Environment Configuration**: Set `VITE_API_BASE_URL=http://localhost:8000` in `frontend/.env`.

### Optional: Legacy Streamlit Frontend
The previous Streamlit frontend remains available as a fallback:
```powershell
python -m streamlit run frontend/streamlit_app.py
```
- **Streamlit Interface**: Opens at `http://localhost:8501`.

---

## 6. FastAPI Endpoints & Capabilities

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Service health status and dependency checks (FAISS, Groq, Gnani). |
| `POST` | `/sessions` | Creates a new isolated conversation session. |
| `GET` | `/sessions/{id}` | Retrieves safe session metadata (turn count, verification state). |
| `DELETE` | `/sessions/{id}` | Resets or clears a conversation session's history and state. |
| `POST` | `/chat` | Multi-turn customer text query returning answer, sources, and evidence. |
| `POST` | `/voice` | Multipart audio upload (.wav/.mp3); runs STT → Agent → TTS. Returns transcript, answer, and base64 audio. |
| `GET` | `/audio/{id}` | Streams synthesized `.wav` speech audio directly. |

---

## 7. Running the CLI & Batch Pipelines

### Interactive CLI Chat
```bash
python run.py --interactive
```

### Single Text Query
```bash
python run.py --query "What is the return window for clothing?"
```

### Audio Batch Pipeline (`run_audio.py` / `run.py`)
Processes a folder of customer audio recordings (.wav, .mp3, etc.):
```bash
python run_audio.py --input-dir samples/input --output-dir outputs/voice_run
```

---

## 8. Testing & Evaluation

### Frontend Vitest Suite (19 Tests)
Run the React unit and integration tests:
```bash
cd frontend
npm test
```
**Frontend Test Breakdown**:
- `src/__tests__/api.test.js` (6 tests): Health check, session creation and reset, chat request payload, multipart voice upload with proper MIME type, and error propagation.
- `src/__tests__/useConversation.test.jsx` (4 tests): Mount initialization, multi-turn chat handling, isolated backend session resets, and duplicate audio submission prevention.
- `src/__tests__/components.test.jsx` (9 tests): Welcome screen and suggestion cards, collapsed-by-default evidence panel, citation display, empty source suppression, per-message source isolation, recording status indicator, preview/discard/submit controls, and tts_generated audio replies.

### Complete Backend Regression Suite
Run all Python automated tests locally without incurring external paid API calls:
```bash
python -m unittest discover -s tests -p "test_*.py"
```

**Test Suite Breakdown**:
- `tests/test_api.py` (14 tests): Health check, session creation/isolation, text chat validation, empty message 422, invalid session 404, evidence preservation, voice format validation, oversized audio rejection (413), mocked STT→Agent→TTS, empty transcription 400, TTS failure fallback, tool security gating, and credential leak prevention.
- `tests/test_frontend_client.py` (6 tests): Frontend client endpoints, connection error handling, non-success status codes, response parsing, session ID retention, and voice upload handling.
- `tests/test_text_agent.py` (12 tests): Grounded RAG retrieval, policy versioning (current vs superseded), Hinglish queries, phone suffix verification gates, business day timelines, and escalation ticket creation.
- `tests/test_voice_agent.py` (15 tests): Gnani STT client parameter handling, Gnani TTS synthesis, batch runner execution, session isolation flags, and audio format validation.

### Dataset Integrity Validation
```bash
python dataset/validate_dataset.py
```

### Multi-Turn Practice Dataset Evaluation (96 Turns)
```bash
python evaluate_agent.py
```

---

## 9. Known Limitations

1. **In-Memory Session Persistence**: Sessions are managed in-process memory. Restarting the FastAPI server clears active sessions. In a distributed multi-worker production setup, an external shared cache (e.g. Redis) is recommended.
2. **Audio Upload Sizing**: The FastAPI backend enforces a maximum audio file upload limit of 15MB to protect memory.
3. **Discrete Turns**: Voice interactions are currently processed turn-by-turn via REST audio uploads rather than continuous full-duplex WebSocket audio streaming.
