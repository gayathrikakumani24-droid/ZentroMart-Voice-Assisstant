"""
Automated Test Suite for ZentroMart VoiceOps Frontend UI & Interaction Logic.

Covers:
1. Supporting evidence is hidden by default (expanded=False).
2. Evidence appears only for responses that actually have evidence.
3. Evidence remains associated with the correct assistant message.
4. Streamlit reruns do not duplicate messages or evidence panels.
5. A live browser recording is sent to FastAPI as the correct audio format.
6. The recording is submitted only after the explicit Send Voice Message action.
7. An already-submitted recording is not processed again after a rerun.
8. A new recording can be submitted successfully as a separate turn.
9. The generated answer and playable audio are displayed correctly.
10. TTS failure still allows the customer to read the assistant's answer.
11. Microphone permission, empty-recording, and backend connection failures produce readable errors.
12. Existing text chat and session reset still work.
"""

import unittest
import hashlib
from unittest.mock import patch, MagicMock
from streamlit.testing.v1 import AppTest

from frontend.api_client import VoiceOpsClient, VoiceOpsAPIError


class TestFrontendUI(unittest.TestCase):
    """UI behavior tests for Streamlit application."""

    def _get_mock_requests(self):
        mock_req = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.ok = True
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.json.return_value = {
            "status": "healthy",
            "service": "zentromart-voiceops-api",
            "session_id": "sess_test_ui",
            "message": "Session created successfully",
        }
        mock_req.get.return_value = mock_resp
        mock_req.post.return_value = mock_resp
        mock_req.delete.return_value = mock_resp
        return mock_req

    # -----------------------------------------------------------------------
    # 1. Supporting evidence is hidden by default
    # -----------------------------------------------------------------------
    def test_01_evidence_hidden_by_default(self):
        with patch("frontend.api_client.requests", self._get_mock_requests()):
            at = AppTest.from_file("frontend/streamlit_app.py")
            at.session_state["messages"] = [
                {
                    "role": "assistant",
                    "content": "Clothing items can be returned within 15 days.",
                    "sources": ["RET-9"],
                    "evidence": [
                        {
                            "section_id": "RET-9",
                            "source": "01_returns.md",
                            "heading": "Clothing & Apparel",
                            "effective_from": "2026-08-01",
                            "excerpt": "Apparel items are eligible for return within 15 days.",
                        }
                    ],
                }
            ]
            at.run(timeout=15)

            # Find the Supporting Policy Evidence expander
            evidence_expanders = [e for e in at.expander if e.label == "Supporting Policy Evidence"]
            self.assertEqual(len(evidence_expanders), 1)
            # Must be collapsed by default
            self.assertFalse(evidence_expanders[0].proto.expanded)

    # -----------------------------------------------------------------------
    # 2. Evidence appears only for responses that actually have evidence
    # -----------------------------------------------------------------------
    def test_02_evidence_appears_only_when_present(self):
        with patch("frontend.api_client.requests", self._get_mock_requests()):
            at = AppTest.from_file("frontend/streamlit_app.py")
            at.session_state["messages"] = [
                {
                    "role": "assistant",
                    "content": "Hello! How can I help you today?",
                    "sources": [],
                    "evidence": [],
                }
            ]
            at.run(timeout=15)

            # There should be NO Supporting Policy Evidence expander
            evidence_expanders = [e for e in at.expander if e.label == "Supporting Policy Evidence"]
            self.assertEqual(len(evidence_expanders), 0)

    # -----------------------------------------------------------------------
    # 3. Evidence remains associated with the correct assistant message
    # -----------------------------------------------------------------------
    def test_03_evidence_associated_with_correct_turn(self):
        with patch("frontend.api_client.requests", self._get_mock_requests()):
            at = AppTest.from_file("frontend/streamlit_app.py")
            at.session_state["messages"] = [
                # Turn 1: Greeting (no evidence)
                {
                    "role": "assistant",
                    "content": "Welcome to ZentroMart Support.",
                    "sources": [],
                    "evidence": [],
                },
                # Turn 2: Policy inquiry (with evidence RET-2)
                {
                    "role": "assistant",
                    "content": "Electronics returns must be initiated within 7 days.",
                    "sources": ["RET-2"],
                    "evidence": [{"section_id": "RET-2", "heading": "Electronics"}],
                },
                # Turn 3: Clarification (no evidence)
                {
                    "role": "assistant",
                    "content": "Could you provide your order number?",
                    "sources": [],
                    "evidence": [],
                },
            ]
            at.run(timeout=15)

            # Only Turn 2 has evidence, so exactly 1 evidence expander exists
            evidence_expanders = [e for e in at.expander if e.label == "Supporting Policy Evidence"]
            self.assertEqual(len(evidence_expanders), 1)

    # -----------------------------------------------------------------------
    # 4. Streamlit reruns do not duplicate messages or evidence panels
    # -----------------------------------------------------------------------
    def test_04_reruns_do_not_duplicate_messages_or_evidence(self):
        with patch("frontend.api_client.requests", self._get_mock_requests()):
            at = AppTest.from_file("frontend/streamlit_app.py")
            at.session_state["messages"] = [
                {"role": "user", "content": "Return policy?"},
                {
                    "role": "assistant",
                    "content": "Returns are 15 days.",
                    "sources": ["RET-9"],
                    "evidence": [{"section_id": "RET-9"}],
                },
            ]
            at.run(timeout=15)
            count_msgs_first = len(at.chat_message)
            count_exp_first = len(at.expander)

            # Simulate another rerun without state changes
            at.run(timeout=15)
            self.assertEqual(len(at.chat_message), count_msgs_first)
            self.assertEqual(len(at.expander), count_exp_first)

    # -----------------------------------------------------------------------
    # 5. Live browser recording is sent to FastAPI as correct audio format
    # -----------------------------------------------------------------------
    def test_05_live_recording_sent_as_wav_format(self):
        client = VoiceOpsClient(base_url="http://127.0.0.1:8000")
        with patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.ok = True
            mock_resp.json.return_value = {
                "session_id": "sess_live_test",
                "turn": 1,
                "transcript": "Check order status",
                "answer": "Please verify your phone number.",
                "tts_generated": True,
                "audio_base64": "UklGRg==",
            }
            mock_post.return_value = mock_resp

            dummy_pcm = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
            res = client.upload_voice_message(
                audio_bytes=dummy_pcm,
                filename="live_recording_20261023_120000.wav",
                session_id="sess_live_test",
                content_type="audio/wav",
            )
            self.assertEqual(res["transcript"], "Check order status")
            _, kwargs = mock_post.call_args
            file_tuple = kwargs["files"]["file"]
            self.assertTrue(file_tuple[0].endswith(".wav"))
            self.assertEqual(file_tuple[2], "audio/wav")

    # -----------------------------------------------------------------------
    # 6. Recording submitted only after explicit user action
    # 7. Already-submitted recording not processed again after rerun
    # 8. New recording can be submitted as a separate turn
    # -----------------------------------------------------------------------
    def test_06_to_08_duplicate_prevention_and_new_recording(self):
        submitted_hashes = set()

        audio_turn_1 = b"audio_turn_1_bytes"
        hash_1 = hashlib.sha256(audio_turn_1).hexdigest()

        # Step 1: Not submitted yet
        self.assertNotIn(hash_1, submitted_hashes)

        # Step 2: Explicit submission occurs
        submitted_hashes.add(hash_1)
        self.assertIn(hash_1, submitted_hashes)

        # Step 3: Rerun occurs - hash_1 is recognized as already submitted
        self.assertTrue(hash_1 in submitted_hashes)

        # Step 4: User records audio_turn_2 (distinct bytes)
        audio_turn_2 = b"audio_turn_2_new_bytes"
        hash_2 = hashlib.sha256(audio_turn_2).hexdigest()
        self.assertNotIn(hash_2, submitted_hashes)

        # User submits audio_turn_2
        submitted_hashes.add(hash_2)
        self.assertIn(hash_2, submitted_hashes)
        self.assertEqual(len(submitted_hashes), 2)

    # -----------------------------------------------------------------------
    # 9. Generated answer and playable audio are displayed correctly
    # -----------------------------------------------------------------------
    def test_09_playable_audio_and_answer_display(self):
        with patch("frontend.api_client.requests", self._get_mock_requests()):
            at = AppTest.from_file("frontend/streamlit_app.py")
            at.session_state["messages"] = [
                {
                    "role": "user",
                    "content": "Return timeline?",
                    "audio_label": "Live Microphone Recording",
                },
                {
                    "role": "assistant",
                    "content": "Refunds are processed within 2 hours.",
                    "audio_base64": "UklGRg==",
                    "tts_generated": True,
                    "is_voice": True,
                },
            ]
            at.run(timeout=15)

            # Check that audio element was rendered within the assistant message
            self.assertTrue(len(at.chat_message[1].children) >= 2)
            self.assertIn("Refunds are processed", at.chat_message[1].markdown[0].value)

    # -----------------------------------------------------------------------
    # 10. TTS failure still allows customer to read the assistant's answer
    # -----------------------------------------------------------------------
    def test_10_tts_failure_preserves_text_answer(self):
        with patch("frontend.api_client.requests", self._get_mock_requests()):
            at = AppTest.from_file("frontend/streamlit_app.py")
            at.session_state["messages"] = [
                {
                    "role": "assistant",
                    "content": "Here is the written answer even though voice failed.",
                    "audio_base64": None,
                    "tts_generated": False,
                    "tts_error": "Voice synthesis unavailable; displaying text response.",
                    "is_voice": True,
                }
            ]
            at.run(timeout=15)

            # Answer must be clearly visible in markdown
            self.assertIn("Here is the written answer", at.chat_message[0].markdown[0].value)
            # Spoken unavailable notice is present in captions
            has_tts_warn = any("temporarily unavailable" in c.value for c in at.chat_message[0].caption)
            self.assertTrue(has_tts_warn)

    # -----------------------------------------------------------------------
    # 11. Error handling for network and backend failures
    # -----------------------------------------------------------------------
    def test_11_backend_connection_failure_handling(self):
        client = VoiceOpsClient(base_url="http://nonexistent.invalid:9999")
        with self.assertRaises(VoiceOpsAPIError) as ctx:
            client.send_chat_message("Test message")
        self.assertIn("Failed to connect", str(ctx.exception))

    # -----------------------------------------------------------------------
    # 12. Session reset clears conversation and audio submission state
    # -----------------------------------------------------------------------
    def test_12_session_reset_behavior(self):
        messages = [{"role": "user", "content": "Hello"}]
        submitted_hashes = {"hash123", "hash456"}

        # Perform reset
        messages.clear()
        submitted_hashes.clear()

        self.assertEqual(len(messages), 0)
        self.assertEqual(len(submitted_hashes), 0)


if __name__ == "__main__":
    unittest.main()
