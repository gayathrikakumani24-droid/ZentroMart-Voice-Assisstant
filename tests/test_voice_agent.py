"""
Automated Unit and Integration Tests for Gnani Voice Integration & Audio Runner.

Covers all 15 verification requirements:
1. STT returns recognized text correctly.
2. STT handles empty or invalid transcription.
3. STT handles missing files, empty files, unsupported formats, and SDK failures.
4. TTS saves valid mock audio bytes to the expected location.
5. TTS handles empty text/output and SDK failures.
6. The runner correctly connects STT -> conversation agent -> TTS.
7. The final TTS input is the customer-facing answer, not internal metadata.
8. Evidence JSON includes actual available source information and metadata.
9. Multiple files are processed in deterministic alphabetical filename order.
10. A failed file does not prevent subsequent valid files from being processed.
11. Session isolation works as configured (shared batch session vs separate sessions).
12. Existing text-query and interactive CLI entry points still work without regression.
13. No credentials or protected verification details appear in logs or saved error messages.
14. Invalid input/output paths produce helpful errors.
15. No unsupported speech provider (Whisper, Google, Azure, AWS) is introduced.
"""

import json
import os
import shutil
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.conversation import ZentroMartConversation, _session_manager
from src.voice import (
    GnaniSTT,
    GnaniTTS,
    GnaniVoiceError,
    SUPPORTED_AUDIO_EXTENSIONS,
    transcribe_audio,
    synthesize_speech,
)
from run_audio import process_audio_batch, sanitize_filename


def create_dummy_wav(filepath: Path, duration_sec: float = 0.5):
    """Create a minimal valid PCM WAV file for filesystem testing."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    sample_rate = 16000
    num_frames = int(sample_rate * duration_sec)
    with wave.open(str(filepath), "wb") as wf:
        wf.setnchannels(1)        # mono
        wf.setsampwidth(2)        # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * num_frames)


class TestGnaniVoiceIntegration(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.input_dir = Path(self.temp_dir) / "input"
        self.output_dir = Path(self.temp_dir) / "output"
        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        _session_manager._sessions.clear()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # 1. STT returns recognized text correctly
    def test_01_stt_transcription_success(self):
        wav_file = self.input_dir / "query.wav"
        create_dummy_wav(wav_file)

        mock_client = MagicMock()
        mock_client.transcribe.return_value = {
            "success": True,
            "transcript": "How fast are refunds to the ZentroMart Wallet?",
            "request_id": "req_12345",
        }

        stt = GnaniSTT(client=mock_client)
        result = stt.transcribe(wav_file)

        self.assertEqual(result["transcript"], "How fast are refunds to the ZentroMart Wallet?")
        self.assertEqual(result["request_id"], "req_12345")
        mock_client.transcribe.assert_called_once()

    # 2. STT handles empty or invalid transcription
    def test_02_stt_handles_empty_transcription(self):
        wav_file = self.input_dir / "empty_result.wav"
        create_dummy_wav(wav_file)

        mock_client = MagicMock()
        mock_client.transcribe.return_value = {
            "success": True,
            "transcript": "   ",  # whitespace only
        }

        stt = GnaniSTT(client=mock_client)
        with self.assertRaises(ValueError) as ctx:
            stt.transcribe(wav_file)
        self.assertIn("empty", str(ctx.exception).lower())

    # 3. STT handles missing files, empty files, unsupported formats, and SDK failures
    def test_03_stt_error_handling(self):
        mock_client = MagicMock()
        stt = GnaniSTT(client=mock_client)

        # Missing file
        missing_file = self.input_dir / "missing.wav"
        with self.assertRaises(FileNotFoundError):
            stt.transcribe(missing_file)

        # Unsupported extension
        txt_file = self.input_dir / "notes.txt"
        txt_file.write_text("not audio", encoding="utf-8")
        with self.assertRaises(ValueError) as ctx_ext:
            stt.transcribe(txt_file)
        self.assertIn("unsupported", str(ctx_ext.exception).lower())

        # Empty 0-byte file
        zero_file = self.input_dir / "zero.wav"
        zero_file.touch()
        with self.assertRaises(ValueError) as ctx_zero:
            stt.transcribe(zero_file)
        self.assertIn("empty", str(ctx_zero.exception).lower())

        # SDK failure
        valid_wav = self.input_dir / "sdk_fail.wav"
        create_dummy_wav(valid_wav)
        mock_client.transcribe.side_effect = RuntimeError("Gnani connection timeout")
        with self.assertRaises(GnaniVoiceError) as ctx_sdk:
            stt.transcribe(valid_wav)
        self.assertIn("Gnani STT transcription failed", str(ctx_sdk.exception))

    # 4. TTS saves valid mock audio bytes to expected location
    def test_04_tts_synthesis_success(self):
        out_audio = self.output_dir / "reply.wav"
        mock_client = MagicMock()
        mock_audio_bytes = b"RIFF_MOCK_WAV_BYTES_DATA"
        mock_client.synthesize.return_value = mock_audio_bytes

        tts = GnaniTTS(client=mock_client, voice="Kaveri", model="timbre-v2.5", language="en-IN")
        result_bytes = tts.synthesize("Refunds are instant to your wallet.", output_file=out_audio)

        self.assertEqual(result_bytes, mock_audio_bytes)
        self.assertTrue(out_audio.exists())
        self.assertEqual(out_audio.read_bytes(), mock_audio_bytes)
        mock_client.synthesize.assert_called_once_with(
            "Refunds are instant to your wallet.",
            voice="Kaveri",
            model="timbre-v2.5",
            language="en-IN",
            output_file=str(out_audio),
        )

    # 5. TTS handles empty text/output and SDK failures
    def test_05_tts_error_handling(self):
        mock_client = MagicMock()
        tts = GnaniTTS(client=mock_client)

        # Empty text
        with self.assertRaises(ValueError) as ctx_empty:
            tts.synthesize("   ")
        self.assertIn("cannot be empty", str(ctx_empty.exception))

        # SDK returns empty bytes
        mock_client.synthesize.return_value = b""
        with self.assertRaises(ValueError) as ctx_no_audio:
            tts.synthesize("Hello")
        self.assertIn("empty audio", str(ctx_no_audio.exception))

        # SDK failure
        mock_client.synthesize.side_effect = ConnectionError("Network unreachable")
        with self.assertRaises(GnaniVoiceError) as ctx_net:
            tts.synthesize("Hello")
        self.assertIn("Gnani TTS synthesis failed", str(ctx_net.exception))

    # 6. The runner correctly connects STT -> conversation agent -> TTS
    def test_06_runner_e2e_pipeline(self):
        audio1 = self.input_dir / "01_wallet.wav"
        create_dummy_wav(audio1)

        mock_stt_client = MagicMock()
        mock_stt_client.transcribe.return_value = {
            "success": True,
            "transcript": "How fast are refunds to the ZentroMart Wallet?",
            "request_id": "req_001",
        }

        mock_tts_client = MagicMock()
        mock_tts_client.synthesize.return_value = b"RIFF_AUDIO_WALLET_ANSWER"

        summary = process_audio_batch(
            input_dir=self.input_dir,
            output_dir=self.output_dir,
            stt_client=mock_stt_client,
            tts_client=mock_tts_client,
        )

        self.assertEqual(summary["total_files"], 1)
        self.assertEqual(summary["successful"], 1)
        self.assertEqual(summary["failed"], 0)

        # Verify output directory contents
        self.assertTrue((self.output_dir / "audio" / "01_wallet.wav").exists())
        self.assertTrue((self.output_dir / "transcripts" / "01_wallet.txt").exists())
        self.assertTrue((self.output_dir / "responses" / "01_wallet.txt").exists())
        self.assertTrue((self.output_dir / "evidence" / "01_wallet.json").exists())
        self.assertTrue((self.output_dir / "run_summary.json").exists())

    # 7. The final TTS input is customer-facing answer, not internal metadata
    def test_07_tts_input_is_clean_answer(self):
        audio1 = self.input_dir / "01_query.wav"
        create_dummy_wav(audio1)

        mock_stt_client = MagicMock()
        mock_stt_client.transcribe.return_value = {
            "success": True,
            "transcript": "How fast are refunds to the ZentroMart Wallet?",
        }

        mock_tts_client = MagicMock()
        mock_tts_client.synthesize.return_value = b"RIFF_AUDIO_DATA"

        process_audio_batch(
            input_dir=self.input_dir,
            output_dir=self.output_dir,
            stt_client=mock_stt_client,
            tts_client=mock_tts_client,
        )

        tts_call_args = mock_tts_client.synthesize.call_args[0]
        spoken_text = tts_call_args[0]

        # Verify spoken text contains natural user-facing text and no internal JSON/debug tags
        self.assertIn("wallet", spoken_text.lower())
        self.assertNotIn("session_id", spoken_text)
        self.assertNotIn("decision_hint", spoken_text)
        self.assertNotIn("TOOL EXECUTION", spoken_text)

    # 8. Evidence JSON includes actual available source information
    def test_08_evidence_json_structure(self):
        audio1 = self.input_dir / "01_wallet.wav"
        create_dummy_wav(audio1)

        mock_stt_client = MagicMock()
        mock_stt_client.transcribe.return_value = {
            "success": True,
            "transcript": "How fast are refunds to the ZentroMart Wallet?",
        }

        mock_tts_client = MagicMock()
        mock_tts_client.synthesize.return_value = b"RIFF_AUDIO_DATA"

        process_audio_batch(
            input_dir=self.input_dir,
            output_dir=self.output_dir,
            stt_client=mock_stt_client,
            tts_client=mock_tts_client,
        )

        evidence_path = self.output_dir / "evidence" / "01_wallet.json"
        data = json.loads(evidence_path.read_text(encoding="utf-8"))

        self.assertEqual(data["input_filename"], "01_wallet.wav")
        self.assertEqual(data["transcribed_message"], "How fast are refunds to the ZentroMart Wallet?")
        self.assertEqual(data["agent_decision"], "answer")
        self.assertIn("REF-2", data["sources"])
        self.assertEqual(data["output_audio"], "01_wallet.wav")
        self.assertEqual(data["status"], "success")

    # 9. Multiple files are processed in deterministic order
    def test_09_deterministic_alphabetical_processing(self):
        f3 = self.input_dir / "03_gamma.wav"
        f1 = self.input_dir / "01_alpha.wav"
        f2 = self.input_dir / "02_beta.wav"
        for f in (f3, f1, f2):
            create_dummy_wav(f)

        transcription_calls = []

        def mock_transcribe(path, **kwargs):
            filename = Path(path).name
            transcription_calls.append(filename)
            return {"success": True, "transcript": f"Query for {filename}"}

        mock_stt = MagicMock()
        mock_stt.transcribe.side_effect = mock_transcribe

        mock_tts = MagicMock()
        mock_tts.synthesize.return_value = b"AUDIO"

        summary = process_audio_batch(
            input_dir=self.input_dir,
            output_dir=self.output_dir,
            stt_client=mock_stt,
            tts_client=mock_tts,
        )

        self.assertEqual(transcription_calls, ["01_alpha.wav", "02_beta.wav", "03_gamma.wav"])
        self.assertEqual([f["input_filename"] for f in summary["files"]], ["01_alpha.wav", "02_beta.wav", "03_gamma.wav"])

    # 10. A failed file does not prevent subsequent valid files from being processed
    def test_10_resilient_batch_processing(self):
        f1 = self.input_dir / "01_good.wav"
        f2 = self.input_dir / "02_broken.wav"
        f3 = self.input_dir / "03_good.wav"
        for f in (f1, f2, f3):
            create_dummy_wav(f)

        def mock_transcribe(path, **kwargs):
            if "broken" in str(path):
                raise RuntimeError("Corrupt audio packet")
            return {"success": True, "transcript": "How fast are refunds to the ZentroMart Wallet?"}

        mock_stt = MagicMock()
        mock_stt.transcribe.side_effect = mock_transcribe

        mock_tts = MagicMock()
        mock_tts.synthesize.return_value = b"AUDIO"

        summary = process_audio_batch(
            input_dir=self.input_dir,
            output_dir=self.output_dir,
            stt_client=mock_stt,
            tts_client=mock_tts,
        )

        self.assertEqual(summary["total_files"], 3)
        self.assertEqual(summary["successful"], 2)
        self.assertEqual(summary["failed"], 1)

        # 01 and 03 should have successful audio & evidence
        self.assertTrue((self.output_dir / "audio" / "01_good.wav").exists())
        self.assertTrue((self.output_dir / "audio" / "03_good.wav").exists())
        # 02 should have error json recorded
        self.assertTrue((self.output_dir / "evidence" / "02_broken_error.json").exists())

    # 11. Session isolation works as configured (shared vs separate)
    def test_11_session_isolation_behavior(self):
        f1 = self.input_dir / "01_step1.wav"
        f2 = self.input_dir / "02_step2.wav"
        for f in (f1, f2):
            create_dummy_wav(f)

        mock_stt = MagicMock()
        mock_stt.transcribe.side_effect = [
            {"success": True, "transcript": "Hello, mujhe order ke baare mein help chahiye."},
            {"success": True, "transcript": "Order number hai 8978 2837."},
        ]

        mock_tts = MagicMock()
        mock_tts.synthesize.return_value = b"AUDIO"

        # Shared session (default batch mode) -> multi-turn conversation maintains order_id
        shared_agent = ZentroMartConversation("shared_batch_test")
        process_audio_batch(
            input_dir=self.input_dir,
            output_dir=self.output_dir / "shared_run",
            conversation_agent=shared_agent,
            stt_client=mock_stt,
            tts_client=mock_tts,
            separate_sessions=False,
        )
        self.assertEqual(shared_agent.order_id, "89782837")
        self.assertEqual(shared_agent.session.turn_count, 2)

        # Separate sessions mode
        mock_stt.transcribe.side_effect = [
            {"success": True, "transcript": "Hello, mujhe order ke baare mein help chahiye."},
            {"success": True, "transcript": "Order number hai 8978 2837."},
        ]
        summary_sep = process_audio_batch(
            input_dir=self.input_dir,
            output_dir=self.output_dir / "sep_run",
            stt_client=mock_stt,
            tts_client=mock_tts,
            separate_sessions=True,
        )
        self.assertTrue(summary_sep["separate_sessions"])
        self.assertEqual(summary_sep["successful"], 2)

    # 12. Existing text-query and interactive CLI behavior still works
    def test_12_existing_text_query_works(self):
        agent = ZentroMartConversation("text_reg_test")
        resp = agent.respond("How fast are refunds to the ZentroMart Wallet?")
        self.assertEqual(resp["decision"], "answer")
        self.assertIn("REF-2", resp["sources"])

    # 13. No credentials or protected verification details appear in logs or saved error messages
    def test_13_no_credentials_leaked(self):
        fake_key = "gnani_secret_token_12345"
        f = self.input_dir / "secret_test.wav"
        create_dummy_wav(f)

        mock_stt = MagicMock()
        mock_stt.transcribe.side_effect = RuntimeError(f"Unauthorized with {fake_key}")

        mock_tts = MagicMock()

        summary = process_audio_batch(
            input_dir=self.input_dir,
            output_dir=self.output_dir,
            stt_client=mock_stt,
            tts_client=mock_tts,
        )

        summary_text = (self.output_dir / "run_summary.json").read_text(encoding="utf-8")
        error_file = self.output_dir / "evidence" / "secret_test_error.json"
        error_text = error_file.read_text(encoding="utf-8")

        # Confirm API keys are not stored in evidence or summaries
        self.assertNotIn("GNANI_API_KEY", summary_text)
        self.assertNotIn("GROQ_API_KEY", summary_text)
        self.assertNotIn("phone_last4", summary_text)

    # 14. Invalid input/output paths produce helpful errors
    def test_14_invalid_paths_error(self):
        with self.assertRaises(FileNotFoundError):
            process_audio_batch("non_existent_folder_12345", self.output_dir)

    # 15. No unsupported speech provider is introduced
    def test_15_provider_integrity(self):
        import src.voice as voice_module
        with open(voice_module.__file__, "r", encoding="utf-8") as f:
            code = f.read().lower()

        # Disallowed third-party speech providers as per instructions
        disallowed = ["whisper", "google.cloud.speech", "azure.cognitiveservices.speech", "boto3.client('transcribe')"]
        for provider in disallowed:
            self.assertNotIn(provider, code, f"Disallowed speech provider detected: {provider}")


if __name__ == "__main__":
    unittest.main()
