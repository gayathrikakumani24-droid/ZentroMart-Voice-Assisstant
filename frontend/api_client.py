"""
ZentroMart VoiceOps — API Client for FastAPI Backend.

Handles all HTTP communication with the backend service.
Keeps secret handling and AI pipeline invocations strictly on the backend.
"""

import os
import requests
from typing import Dict, Any, Optional

DEFAULT_BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")


class VoiceOpsAPIError(Exception):
    """Exception raised when FastAPI backend returns an error."""
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class VoiceOpsClient:
    """HTTP Client for ZentroMart VoiceOps FastAPI backend."""

    def __init__(self, base_url: Optional[str] = None, timeout: int = 35):
        self.base_url = (base_url or DEFAULT_BACKEND_URL).rstrip("/")
        self.timeout = timeout

    def check_health(self) -> Dict[str, Any]:
        """Check the health status of the backend service."""
        url = f"{self.base_url}/health"
        try:
            resp = requests.get(url, timeout=5)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as exc:
            return {"status": "unreachable", "error": str(exc)}

    def create_session(self) -> str:
        """Create a new conversation session and return the session ID."""
        url = f"{self.base_url}/sessions"
        try:
            resp = requests.post(url, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            return data["session_id"]
        except requests.exceptions.RequestException as exc:
            raise VoiceOpsAPIError(f"Failed to create session: {exc}") from exc

    def get_session_metadata(self, session_id: str) -> Dict[str, Any]:
        """Fetch metadata for an active session."""
        url = f"{self.base_url}/sessions/{session_id}"
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 404:
                return {"exists": False}
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as exc:
            raise VoiceOpsAPIError(f"Failed to fetch session metadata: {exc}") from exc

    def reset_session(self, session_id: str) -> bool:
        """Reset or clear a conversation session on the backend."""
        url = f"{self.base_url}/sessions/{session_id}"
        try:
            resp = requests.delete(url, timeout=self.timeout)
            if resp.status_code == 404:
                return False
            resp.raise_for_status()
            return True
        except requests.exceptions.RequestException as exc:
            raise VoiceOpsAPIError(f"Failed to reset session: {exc}") from exc

    def send_chat_message(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Send a text inquiry to the backend conversation agent."""
        url = f"{self.base_url}/chat"
        payload = {"message": message, "session_id": session_id}
        try:
            resp = requests.post(url, json=payload, timeout=self.timeout)
            if not resp.ok:
                detail = resp.json().get("detail", resp.text) if resp.headers.get("content-type", "").startswith("application/json") else resp.text
                raise VoiceOpsAPIError(detail, status_code=resp.status_code)
            return resp.json()
        except requests.exceptions.RequestException as exc:
            raise VoiceOpsAPIError(f"Failed to connect to backend: {exc}") from exc

    def upload_voice_message(
        self,
        audio_bytes: bytes,
        filename: str = "recording.wav",
        session_id: Optional[str] = None,
        content_type: str = "audio/wav",
    ) -> Dict[str, Any]:
        """Upload customer audio for STT transcription, agent response, and TTS."""
        url = f"{self.base_url}/voice"
        files = {"file": (filename, audio_bytes, content_type)}
        data = {}
        if session_id:
            data["session_id"] = session_id

        try:
            resp = requests.post(url, files=files, data=data, timeout=self.timeout)
            if not resp.ok:
                detail = resp.json().get("detail", resp.text) if resp.headers.get("content-type", "").startswith("application/json") else resp.text
                raise VoiceOpsAPIError(detail, status_code=resp.status_code)
            return resp.json()
        except requests.exceptions.RequestException as exc:
            raise VoiceOpsAPIError(f"Failed to process voice request: {exc}") from exc
