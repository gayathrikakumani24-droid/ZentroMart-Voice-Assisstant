"""
Pydantic Request and Response Schemas for ZentroMart VoiceOps FastAPI Backend.
"""

from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, field_validator


class HealthResponse(BaseModel):
    status: str = Field(..., description="Overall health status (e.g. healthy)")
    service: str = Field("zentromart-voiceops-api", description="Service identifier")
    version: str = Field("1.0.0", description="API version")
    knowledge_base_ready: bool = Field(..., description="Whether FAISS index and chunks are initialized")
    groq_configured: bool = Field(..., description="Whether GROQ_API_KEY is present in environment")
    gnani_configured: bool = Field(..., description="Whether GNANI_API_KEY is present in environment")


class CreateSessionResponse(BaseModel):
    session_id: str = Field(..., description="Unique conversation session identifier")
    message: str = Field("Session created successfully", description="Status message")


class SessionMetadataResponse(BaseModel):
    session_id: str = Field(..., description="Session identifier")
    exists: bool = Field(..., description="Whether the session exists in active memory")
    turn_count: int = Field(0, description="Total turns completed in this session")
    is_verified: bool = Field(False, description="Whether customer order identity has been verified")


class ResetSessionResponse(BaseModel):
    session_id: str = Field(..., description="Session identifier")
    status: str = Field("reset", description="Action status")
    message: str = Field("Session reset successfully", description="Status message")


class ChatRequest(BaseModel):
    session_id: Optional[str] = Field(None, description="Optional existing session ID")
    message: str = Field(..., description="Customer input text query", min_length=1)

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Message cannot be empty or whitespace only.")
        return stripped


class EvidenceItem(BaseModel):
    source: Optional[str] = None
    section_id: Optional[str] = None
    heading: Optional[str] = None
    similarity: Optional[float] = None
    status: Optional[str] = None
    effective_from: Optional[str] = None
    excerpt: Optional[str] = None


class ChatResponse(BaseModel):
    session_id: str = Field(..., description="Active session ID")
    turn: int = Field(..., description="Turn index for this interaction")
    answer: str = Field(..., description="Agent response message")
    decision: str = Field(..., description="Routing decision (e.g. answer, clarify, escalate)")
    sources: List[str] = Field(default_factory=list, description="Cited policy section IDs")
    evidence: List[EvidenceItem] = Field(default_factory=list, description="Retrieved chunk metadata")
    tool_called: bool = Field(False, description="Whether an external tool was invoked")
    tool_action_status: Optional[str] = Field(None, description="Safe summary of tool action")
    ticket_created: bool = Field(False, description="Whether an escalation ticket was created")
    ticket_id: Optional[str] = Field(None, description="Created ticket ID if confirmed")
    is_verified: bool = Field(False, description="Whether customer is verified")
    order_id: Optional[str] = Field(None, description="Current referenced order ID")
    order_status: Optional[str] = Field(None, description="Current delivery/processing status of verified order")


class VoiceResponse(BaseModel):
    session_id: str = Field(..., description="Active session ID")
    turn: int = Field(..., description="Turn index")
    transcript: str = Field(..., description="Recognized customer speech from Gnani STT")
    answer: str = Field(..., description="Agent response message")
    decision: str = Field(..., description="Routing decision")
    sources: List[str] = Field(default_factory=list, description="Cited policy section IDs")
    evidence: List[EvidenceItem] = Field(default_factory=list, description="Retrieved chunk metadata")
    audio_url: Optional[str] = Field(None, description="URL endpoint to stream synthesized audio")
    audio_base64: Optional[str] = Field(None, description="Base64-encoded audio bytes for immediate playback")
    tts_generated: bool = Field(..., description="Whether voice synthesis succeeded")
    error: Optional[str] = Field(None, description="Non-fatal warning or error detail if TTS failed")
    is_verified: bool = Field(False, description="Whether customer is verified")
    order_id: Optional[str] = Field(None, description="Current referenced order ID")
    order_status: Optional[str] = Field(None, description="Current delivery/processing status of verified order")
