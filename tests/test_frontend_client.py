"""
Automated Test Suite for ZentroMart VoiceOps Streamlit API Client.

Covers:
1. Correct backend endpoint and request format.
2. Backend connection failures.
3. Non-success HTTP responses.
4. Response parsing.
5. Session ID retention.
6. Audio-upload request handling.
"""

import unittest
from unittest.mock import patch, MagicMock
import requests

from frontend.api_client import VoiceOpsClient, VoiceOpsAPIError


class TestVoiceOpsClient(unittest.TestCase):
    """Unit tests for the frontend API client."""

    def setUp(self):
        self.client = VoiceOpsClient(base_url="http://testserver:8000")

    # 1. Correct backend endpoint and health check
    @patch("requests.get")
    def test_01_check_health_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "healthy", "service": "zentromart-voiceops-api"}
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        health = self.client.check_health()
        self.assertEqual(health["status"], "healthy")
        mock_get.assert_called_with("http://testserver:8000/health", timeout=5)

    # 2. Backend connection failures
    @patch("requests.get")
    def test_02_backend_connection_failure(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")
        health = self.client.check_health()
        self.assertEqual(health["status"], "unreachable")
        self.assertIn("Connection refused", health["error"])

    # 3. Non-success HTTP responses raise VoiceOpsAPIError
    @patch("requests.post")
    def test_03_non_success_response_handling(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.status_code = 400
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.json.return_value = {"detail": "Message cannot be empty."}
        mock_post.return_value = mock_resp

        with self.assertRaises(VoiceOpsAPIError) as ctx:
            self.client.send_chat_message(message="   ")
        self.assertIn("Message cannot be empty.", str(ctx.exception))
        self.assertEqual(ctx.exception.status_code, 400)

    # 4. Response parsing for chat
    @patch("requests.post")
    def test_04_chat_response_parsing(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {
            "session_id": "sess_123",
            "turn": 1,
            "answer": "Instant wallet refund.",
            "decision": "answer",
            "sources": ["REF-2"],
            "evidence": [],
            "ticket_created": False,
        }
        mock_post.return_value = mock_resp

        res = self.client.send_chat_message(message="Wallet refund timeline?", session_id="sess_123")
        self.assertEqual(res["session_id"], "sess_123")
        self.assertEqual(res["decision"], "answer")
        self.assertEqual(res["sources"], ["REF-2"])

    # 5. Session ID creation and retention
    @patch("requests.post")
    def test_05_session_creation(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"session_id": "sess_abc999", "message": "Created"}
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        sess_id = self.client.create_session()
        self.assertEqual(sess_id, "sess_abc999")
        mock_post.assert_called_with("http://testserver:8000/sessions", timeout=35)

    # 6. Audio-upload request handling
    @patch("requests.post")
    def test_06_audio_upload_request(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {
            "session_id": "sess_xyz",
            "turn": 1,
            "transcript": "Hello ZentroMart",
            "answer": "How can I help you?",
            "tts_generated": True,
            "audio_base64": "UklGRg==",
        }
        mock_post.return_value = mock_resp

        dummy_audio = b"fake-audio-bytes"
        res = self.client.upload_voice_message(
            audio_bytes=dummy_audio,
            filename="user_query.wav",
            session_id="sess_xyz",
        )
        self.assertEqual(res["transcript"], "Hello ZentroMart")
        self.assertTrue(res["tts_generated"])
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "http://testserver:8000/voice")
        self.assertIn("file", kwargs["files"])
        self.assertEqual(kwargs["data"]["session_id"], "sess_xyz")

    # 7. Live browser recording upload with custom content_type
    @patch("requests.post")
    def test_07_live_recording_upload_content_type(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {
            "session_id": "sess_live",
            "turn": 1,
            "transcript": "Return policy for shoes?",
            "answer": "Shoes have a 15-day return window.",
            "tts_generated": True,
            "audio_base64": "UklGRg==",
            "sources": ["RET-9"],
            "evidence": [{"section_id": "RET-9", "heading": "Footwear", "excerpt": "15 days"}],
        }
        mock_post.return_value = mock_resp

        res = self.client.upload_voice_message(
            audio_bytes=b"RIFFwavdata",
            filename="live_recording_20261023.wav",
            session_id="sess_live",
            content_type="audio/wav",
        )
        self.assertEqual(res["transcript"], "Return policy for shoes?")
        self.assertEqual(res["sources"], ["RET-9"])
        self.assertEqual(len(res["evidence"]), 1)
        args, kwargs = mock_post.call_args
        self.assertEqual(kwargs["files"]["file"], ("live_recording_20261023.wav", b"RIFFwavdata", "audio/wav"))

    # 8. Handling voice response when TTS fails but answer succeeds
    @patch("requests.post")
    def test_08_voice_response_when_tts_fails(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {
            "session_id": "sess_tts_fail",
            "turn": 1,
            "transcript": "Where is my refund?",
            "answer": "Wallet refunds take up to 2 hours.",
            "tts_generated": False,
            "audio_base64": None,
            "error": "Voice synthesis unavailable; displaying text response.",
            "sources": ["REF-2"],
        }
        mock_post.return_value = mock_resp

        res = self.client.upload_voice_message(
            audio_bytes=b"fake-bytes",
            filename="query.wav",
            session_id="sess_tts_fail",
        )
        self.assertFalse(res["tts_generated"])
        self.assertIsNone(res["audio_base64"])
        self.assertIn("Wallet refunds", res["answer"])
        self.assertIn("unavailable", res["error"])


if __name__ == "__main__":
    unittest.main()

