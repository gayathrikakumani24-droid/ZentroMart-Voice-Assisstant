"""
ZentroMart VoiceOps — FastAPI Application Main Entry Point.

Endpoints:
- GET  /health                   : Health status and dependency check
- POST /sessions                 : Create a new isolated conversation session
- GET  /sessions/{session_id}    : Retrieve safe session metadata
- DELETE /sessions/{session_id}  : Reset or remove session state
- POST /chat                     : Multi-turn text customer support chat
- POST /voice                    : Voice file upload -> STT -> Agent -> TTS
- GET  /audio/{audio_id}         : Stream synthesized audio
"""

import os
import uuid
import base64
import tempfile
import logging
from pathlib import Path
from typing import Optional, Dict

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, status, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from api.schemas import (
    HealthResponse,
    CreateSessionResponse,
    SessionMetadataResponse,
    ResetSessionResponse,
    ChatRequest,
    ChatResponse,
    VoiceResponse,
    EvidenceItem,
)
from src.conversation import ZentroMartConversation, _session_manager
from src.voice import (
    transcribe_audio,
    synthesize_speech,
    SUPPORTED_AUDIO_EXTENSIONS,
    GnaniVoiceError,
)
from src.knowledge_base import load_knowledge_base

load_dotenv()

logger = logging.getLogger("zentromart_api")
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="ZentroMart VoiceOps API",
    description="Customer Support AI Agent with RAG, Tool Security, and Gnani Voice Pipeline.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Allow local frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8501",
        "http://127.0.0.1:8501",
        "*",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Maximum file upload size: 15MB
MAX_AUDIO_SIZE_BYTES = 15 * 1024 * 1024

# In-memory temporary audio cache for synthesized speech playback
_audio_cache: Dict[str, bytes] = {}


# ---------------------------------------------------------------------------
# Global Exception Handler (Never leak secrets or stack traces to clients)
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception):
    logger.error(f"Unhandled error during {request.method} {request.url.path}: {exc.__class__.__name__}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please try again later."},
    )


# ---------------------------------------------------------------------------
# 1. Health Check
# ---------------------------------------------------------------------------
@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="Check service health and local component readiness",
)
def get_health() -> HealthResponse:
    kb_ready = False
    try:
        index, chunks = load_knowledge_base()
        kb_ready = (index is not None and len(chunks) > 0)
    except Exception:
        kb_ready = False

    return HealthResponse(
        status="healthy",
        service="zentromart-voiceops-api",
        version="1.0.0",
        knowledge_base_ready=kb_ready,
        groq_configured=bool(os.getenv("GROQ_API_KEY")),
        gnani_configured=bool(os.getenv("GNANI_API_KEY")),
    )


# ---------------------------------------------------------------------------
# 2. Session Management
# ---------------------------------------------------------------------------
@app.post(
    "/sessions",
    response_model=CreateSessionResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Sessions"],
    summary="Create a new isolated conversation session",
)
def create_session() -> CreateSessionResponse:
    session = _session_manager.get_or_create_session()
    return CreateSessionResponse(
        session_id=session.session_id,
        message="Session created successfully",
    )


@app.get(
    "/sessions/{session_id}",
    response_model=SessionMetadataResponse,
    tags=["Sessions"],
    summary="Retrieve safe session metadata",
)
def get_session_metadata(session_id: str) -> SessionMetadataResponse:
    if session_id not in _session_manager._sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )
    session = _session_manager._sessions[session_id]
    return SessionMetadataResponse(
        session_id=session.session_id,
        exists=True,
        turn_count=session.turn_count,
        is_verified=session.is_verified,
    )


@app.delete(
    "/sessions/{session_id}",
    response_model=ResetSessionResponse,
    tags=["Sessions"],
    summary="Reset or clear session state",
)
def delete_session(session_id: str) -> ResetSessionResponse:
    if session_id not in _session_manager._sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )
    _session_manager.reset_session(session_id)
    return ResetSessionResponse(
        session_id=session_id,
        status="reset",
        message="Session reset successfully",
    )


# ---------------------------------------------------------------------------
# 3. Chat Endpoint
# ---------------------------------------------------------------------------
@app.post(
    "/chat",
    response_model=ChatResponse,
    tags=["Conversation"],
    summary="Process customer text query through conversation agent",
)
def post_chat(request: ChatRequest) -> ChatResponse:
    try:
        agent = ZentroMartConversation(session_id=request.session_id)
        raw_res = agent.respond(request.message)
    except Exception as exc:
        logger.error(f"Error in conversation agent: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing customer inquiry.",
        )

    # Normalize tool action and ticket statuses safely
    tool_results = raw_res.get("tool_results") or []
    tool_called = len(tool_results) > 0
    tool_status = None
    if tool_called:
        first_tool = tool_results[0]
        tool_status = f"{first_tool.get('tool')}: {first_tool.get('result', {}).get('status', 'executed')}"

    created_ticket = raw_res.get("created_ticket")
    ticket_created = bool(created_ticket and created_ticket.get("created") is True)
    ticket_id = created_ticket.get("ticket_id") if ticket_created else None

    # Parse evidence
    evidence_items = []
    for ev in raw_res.get("evidence") or []:
        evidence_items.append(EvidenceItem(
            source=ev.get("source"),
            section_id=ev.get("section_id"),
            heading=ev.get("heading"),
            similarity=ev.get("similarity"),
            status=ev.get("status"),
            effective_from=ev.get("effective_from"),
            excerpt=ev.get("excerpt") or ev.get("text"),
        ))

    return ChatResponse(
        session_id=raw_res.get("session_id", agent.session_id),
        turn=raw_res.get("turn", agent.session.turn_count),
        answer=raw_res.get("answer", ""),
        decision=raw_res.get("decision", "answer"),
        sources=raw_res.get("sources") or [],
        evidence=evidence_items,
        tool_called=tool_called,
        tool_action_status=tool_status,
        ticket_created=ticket_created,
        ticket_id=ticket_id,
        is_verified=bool(raw_res.get("is_verified")),
        order_id=raw_res.get("order_id"),
        order_status=raw_res.get("order_status"),
    )


# ---------------------------------------------------------------------------
# 4. Voice Endpoint (STT -> Agent -> TTS)
# ---------------------------------------------------------------------------
@app.post(
    "/voice",
    response_model=VoiceResponse,
    tags=["VoiceOps"],
    summary="Process customer voice query via Gnani STT, Agent, and Gnani TTS",
)
async def post_voice(
    file: UploadFile = File(..., description="Customer audio file"),
    session_id: Optional[str] = Form(None, description="Optional conversation session ID"),
) -> VoiceResponse:
    # 1. Validate filename and extension
    raw_filename = file.filename or "recording.wav"
    file_ext = Path(raw_filename).suffix.lower()

    if not file_ext or file_ext not in SUPPORTED_AUDIO_EXTENSIONS:
        content_type = (file.content_type or "").lower().split(";")[0].strip()
        mime_to_ext = {
            "audio/wav": ".wav",
            "audio/x-wav": ".wav",
            "audio/wave": ".wav",
            "audio/mp3": ".mp3",
            "audio/mpeg": ".mp3",
            "audio/ogg": ".ogg",
            "audio/flac": ".flac",
            "audio/x-flac": ".flac",
            "audio/aac": ".aac",
            "audio/m4a": ".m4a",
            "audio/mp4": ".m4a",
            "audio/x-m4a": ".m4a",
        }
        if content_type in mime_to_ext:
            file_ext = mime_to_ext[content_type]

    if file_ext not in SUPPORTED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported audio format '{file_ext or raw_filename}'. Supported formats: {sorted(list(SUPPORTED_AUDIO_EXTENSIONS))}",
        )

    # 2. Read and validate content size
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded audio file is empty (0 bytes).",
        )
    if len(content) > MAX_AUDIO_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Audio file exceeds maximum size limit of {MAX_AUDIO_SIZE_BYTES // (1024 * 1024)}MB.",
        )

    # 3. Save to temporary file for STT processing
    temp_dir = tempfile.gettempdir()
    temp_input = Path(temp_dir) / f"stt_input_{uuid.uuid4().hex}{file_ext}"
    try:
        temp_input.write_bytes(content)

        # 4. Transcribe using Gnani STT
        try:
            transcript = transcribe_audio(temp_input)
        except GnaniVoiceError as exc:
            logger.error(f"Gnani STT error: {exc}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Speech recognition failed. Please ensure GNANI_API_KEY is configured.",
            )
        except Exception as exc:
            logger.error(f"Unexpected STT error: {exc}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error processing speech recognition.",
            )

        if not transcript or not transcript.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Transcription returned empty text. Please speak clearly and try again.",
            )

        # 5. Process through Conversation Agent
        agent = ZentroMartConversation(session_id=session_id)
        raw_res = agent.respond(transcript.strip())

        answer = raw_res.get("answer", "")
        decision = raw_res.get("decision", "answer")
        sources = raw_res.get("sources") or []

        # Parse evidence
        evidence_items = []
        for ev in raw_res.get("evidence") or []:
            evidence_items.append(EvidenceItem(
                source=ev.get("source"),
                section_id=ev.get("section_id"),
                heading=ev.get("heading"),
                similarity=ev.get("similarity"),
                status=ev.get("status"),
                effective_from=ev.get("effective_from"),
                excerpt=ev.get("excerpt") or ev.get("text"),
            ))

        # 6. Synthesize Spoken Answer via Gnani TTS (voice: Kaveri, model: timbre-v2.5)
        audio_id = None
        audio_b64 = None
        tts_ok = False
        tts_error = None

        temp_output = Path(temp_dir) / f"tts_output_{uuid.uuid4().hex}.wav"
        try:
            synthesize_speech(answer, output_path=temp_output)
            if temp_output.exists() and temp_output.stat().st_size > 0:
                audio_bytes = temp_output.read_bytes()
                audio_id = f"audio_{uuid.uuid4().hex[:12]}.wav"
                _audio_cache[audio_id] = audio_bytes
                audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
                tts_ok = True
        except Exception as exc:
            logger.warning(f"Gnani TTS failed, returning text answer: {exc}")
            tts_ok = False
            tts_error = "Voice synthesis unavailable; displaying text response."
        finally:
            if temp_output.exists():
                try:
                    temp_output.unlink()
                except OSError:
                    pass

        return VoiceResponse(
            session_id=raw_res.get("session_id", agent.session_id),
            turn=raw_res.get("turn", agent.session.turn_count),
            transcript=transcript.strip(),
            answer=answer,
            decision=decision,
            sources=sources,
            evidence=evidence_items,
            audio_url=f"/audio/{audio_id}" if audio_id else None,
            audio_base64=audio_b64,
            tts_generated=tts_ok,
            error=tts_error,
            is_verified=bool(raw_res.get("is_verified")),
            order_id=raw_res.get("order_id"),
            order_status=raw_res.get("order_status"),
        )

    finally:
        # Clean up temporary uploaded file
        if temp_input.exists():
            try:
                temp_input.unlink()
            except OSError:
                pass


# ---------------------------------------------------------------------------
# 5. Audio Stream Endpoint
# ---------------------------------------------------------------------------
@app.get(
    "/audio/{audio_id}",
    tags=["VoiceOps"],
    summary="Stream synthesized speech audio file",
)
def get_audio(audio_id: str):
    if audio_id not in _audio_cache:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio resource not found or expired.",
        )
    return Response(
        content=_audio_cache[audio_id],
        media_type="audio/wav",
    )


# ---------------------------------------------------------------------------
# 6. Optional Static SPA Mount (Unified Single-Service Deployment)
# ---------------------------------------------------------------------------
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    from fastapi.staticfiles import StaticFiles
    from starlette.responses import FileResponse

    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="frontend_assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_frontend_spa(full_path: str):
        # Allow API endpoints and docs to proceed unimpeded
        if full_path.startswith(("api", "docs", "redoc", "openapi.json", "audio")):
            raise HTTPException(status_code=404, detail="Not Found")
        file_path = FRONTEND_DIST / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIST / "index.html")
