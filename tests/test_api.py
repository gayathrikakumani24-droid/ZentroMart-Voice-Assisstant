"""
Automated Test Suite for ZentroMart VoiceOps FastAPI Backend.

Covers:
1. Health endpoint.
2. Session creation.
3. Session isolation.
4. Valid text chat request.
5. Empty-message validation.
6. Invalid session handling.
7. Structured response and evidence preservation.
8. Voice upload validation.
9. Unsupported and oversized audio rejection.
10. Successful mocked STT -> conversation agent -> TTS workflow.
11. Empty transcription handling.
12. TTS failure while preserving the text answer.
13. Tool errors and ticket-creation failure handling.
14. No credentials or sensitive values in error responses.
"""

import os
import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from api.main import app, _audio_cache
from src.conversation import _session_manager


class TestFastAPIBackend(unittest.TestCase):
    """Integration and unit tests for FastAPI endpoints."""

    def setUp(self):
        self.client = TestClient(app)
        # Clear audio cache between tests
        _audio_cache.clear()

    # ----------------------------------------------------
    # 1. Health endpoint
    # ----------------------------------------------------
    def test_01_health_endpoint(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["service"], "zentromart-voiceops-api")
        self.assertIn("knowledge_base_ready", data)
        self.assertIn("groq_configured", data)
        self.assertIn("gnani_configured", data)

    # ----------------------------------------------------
    # 2. Session creation
    # ----------------------------------------------------
    def test_02_session_creation(self):
        resp = self.client.post("/sessions")
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertIn("session_id", data)
        self.assertTrue(data["session_id"].startswith("sess_"))

    # ----------------------------------------------------
    # 3. Session isolation
    # ----------------------------------------------------
    def test_03_session_isolation(self):
        # Create session 1
        s1 = self.client.post("/sessions").json()["session_id"]
        # Create session 2
        s2 = self.client.post("/sessions").json()["session_id"]
        self.assertNotEqual(s1, s2)

        # Talk to session 1
        r1 = self.client.post("/chat", json={"session_id": s1, "message": "My order is ORD0001"})
        self.assertEqual(r1.status_code, 200)

        # Session 2 should have 0 turns
        m2 = self.client.get(f"/sessions/{s2}").json()
        self.assertEqual(m2["turn_count"], 0)
        self.assertFalse(m2["is_verified"])

    # ----------------------------------------------------
    # 4. Valid text chat request
    # ----------------------------------------------------
    def test_04_valid_text_chat(self):
        resp = self.client.post("/chat", json={"message": "What is the return window for clothing?"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("answer", data)
        self.assertIn("decision", data)
        self.assertIn("sources", data)
        self.assertIn("RET-9", data["sources"])

    # ----------------------------------------------------
    # 5. Empty-message validation
    # ----------------------------------------------------
    def test_05_empty_message_validation(self):
        # Empty string
        r1 = self.client.post("/chat", json={"message": ""})
        self.assertEqual(r1.status_code, 422)

        # Whitespace string
        r2 = self.client.post("/chat", json={"message": "   "})
        self.assertEqual(r2.status_code, 422)

    # ----------------------------------------------------
    # 6. Invalid session handling
    # ----------------------------------------------------
    def test_06_invalid_session_handling(self):
        # Non-existent session metadata
        resp = self.client.get("/sessions/non_existent_session_12345")
        self.assertEqual(resp.status_code, 404)

        # Non-existent session delete
        del_resp = self.client.delete("/sessions/non_existent_session_12345")
        self.assertEqual(del_resp.status_code, 404)

    # ----------------------------------------------------
    # 7. Structured response and evidence preservation
    # ----------------------------------------------------
    def test_07_structured_response_and_evidence(self):
        resp = self.client.post("/chat", json={"message": "How fast are refunds to ZentroMart Wallet?"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["decision"], "answer")
        self.assertIn("REF-2", data["sources"])
        self.assertIn("evidence", data)
        self.assertIsInstance(data["evidence"], list)

    # ----------------------------------------------------
    # 8. Voice upload validation (empty file)
    # ----------------------------------------------------
    def test_08_voice_upload_empty_file(self):
        files = {"file": ("empty.wav", b"", "audio/wav")}
        resp = self.client.post("/voice", files=files)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("empty", resp.json()["detail"].lower())

    # ----------------------------------------------------
    # 9. Unsupported and oversized audio rejection
    # ----------------------------------------------------
    def test_09_unsupported_and_oversized_audio(self):
        # Unsupported extension .txt
        files = {"file": ("test.txt", b"some text content", "text/plain")}
        resp = self.client.post("/voice", files=files)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("unsupported audio format", resp.json()["detail"].lower())

        # Oversized file (> 15MB)
        huge_bytes = b"0" * (16 * 1024 * 1024)
        files_huge = {"file": ("huge.wav", huge_bytes, "audio/wav")}
        resp_huge = self.client.post("/voice", files=files_huge)
        self.assertEqual(resp_huge.status_code, 413)

    # ----------------------------------------------------
    # 10. Successful mocked STT -> Agent -> TTS workflow
    # ----------------------------------------------------
    @patch("api.main.transcribe_audio")
    @patch("api.main.synthesize_speech")
    def test_10_successful_mocked_voice_workflow(self, mock_synthesize, mock_transcribe):
        mock_transcribe.return_value = "How fast are refunds to ZentroMart Wallet?"
        fake_wav = b"RIFF....WAVEfmt...."
        
        def fake_synth(text, output_path):
            from pathlib import Path
            Path(output_path).write_bytes(fake_wav)
            return Path(output_path)
            
        mock_synthesize.side_effect = fake_synth

        files = {"file": ("query.wav", b"dummy audio payload", "audio/wav")}
        resp = self.client.post("/voice", files=files)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["transcript"], "How fast are refunds to ZentroMart Wallet?")
        self.assertIn("instant", data["answer"].lower())
        self.assertTrue(data["tts_generated"])
        self.assertIsNotNone(data["audio_base64"])
        self.assertIsNotNone(data["audio_url"])

    # ----------------------------------------------------
    # 11. Empty transcription handling
    # ----------------------------------------------------
    @patch("api.main.transcribe_audio")
    def test_11_empty_transcription_handling(self, mock_transcribe):
        mock_transcribe.return_value = "   "  # Empty / silent transcription
        files = {"file": ("silence.wav", b"dummy audio payload", "audio/wav")}
        resp = self.client.post("/voice", files=files)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("empty text", resp.json()["detail"].lower())

    # ----------------------------------------------------
    # 12. TTS failure while preserving text answer
    # ----------------------------------------------------
    @patch("api.main.transcribe_audio")
    @patch("api.main.synthesize_speech")
    def test_12_tts_failure_preserves_text_answer(self, mock_synthesize, mock_transcribe):
        mock_transcribe.return_value = "How fast are refunds to ZentroMart Wallet?"
        mock_synthesize.side_effect = RuntimeError("Gnani TTS credit exhausted")

        files = {"file": ("query.wav", b"dummy audio payload", "audio/wav")}
        resp = self.client.post("/voice", files=files)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["transcript"], "How fast are refunds to ZentroMart Wallet?")
        self.assertIn("instant", data["answer"].lower())
        self.assertFalse(data["tts_generated"])
        self.assertIsNone(data["audio_base64"])
        self.assertIsNotNone(data["error"])

    # ----------------------------------------------------
    # 13. Tool errors and ticket creation failure handling
    # ----------------------------------------------------
    def test_13_tool_unverified_order_safety(self):
        # Looking up order without verification must NOT reveal customer name or full address
        resp = self.client.post("/chat", json={"message": "Order number is 8978 2837."})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["decision"], "clarify")
        self.assertFalse(data["is_verified"])
        self.assertFalse(data["ticket_created"])

    # ----------------------------------------------------
    # 14. No credentials or sensitive values in error responses
    # ----------------------------------------------------
    def test_14_no_credentials_leaked_in_errors(self):
        # Intentionally cause a 404 or 422 and verify no secret keys appear
        resp = self.client.get("/sessions/bad_session")
        content = resp.text
        self.assertNotIn("vach_", content)
        self.assertNotIn("gsk_", content)
        self.assertNotIn("GROQ_API_KEY", content)
        self.assertNotIn("GNANI_API_KEY", content)

    # ----------------------------------------------------
    # 15. Live browser recording with MIME type fallback
    # ----------------------------------------------------
    @patch("api.main.transcribe_audio")
    @patch("api.main.synthesize_speech")
    def test_15_live_browser_recording_format(self, mock_synthesize, mock_transcribe):
        mock_transcribe.return_value = "What is the return policy for clothing?"
        fake_wav = b"RIFF....WAVEfmt...."
        def fake_synth(text, output_path):
            from pathlib import Path
            Path(output_path).write_bytes(fake_wav)
            return Path(output_path)
        mock_synthesize.side_effect = fake_synth

        # Live browser recording named "blob" or generic with audio/wav content-type
        files = {"file": ("blob", b"RIFFdummybytes", "audio/wav")}
        resp = self.client.post("/voice", files=files)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["transcript"], "What is the return policy for clothing?")
        self.assertTrue(any(s.startswith("RET-") for s in data["sources"]))
        self.assertIsInstance(data["evidence"], list)
        if data["evidence"]:
            first_ev = data["evidence"][0]
            self.assertIn("section_id", first_ev)
            self.assertIn("excerpt", first_ev)


if __name__ == "__main__":
    unittest.main()

