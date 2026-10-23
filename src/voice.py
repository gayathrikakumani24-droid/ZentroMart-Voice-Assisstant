"""
ZentroMart VoiceOps Voice Integration Module — Gnani.ai STT & TTS.

Features:
- Speech-to-Text (STT) using Gnani.ai (gnani.stt.GnaniSTTClient)
  - Default language: en-IN
  - Supported audio formats: .wav, .mp3, .ogg, .flac, .aac, .m4a
  - Rigorous input validation (existence, non-empty, supported extension)
  - SDK response parsing and robust exception handling
- Text-to-Speech (TTS) using Gnani.ai (gnani.tts.GnaniTTSClient)
  - Default voice: Kaveri
  - Default model: timbre-v2.5
  - Default language: en-IN
  - File persistence with automated directory creation and non-empty byte checks
- Zero credential logging and easy mockability for tests.
"""

import os
from pathlib import Path
from typing import Optional, Union, Dict, Any
from dotenv import load_dotenv

load_dotenv()

# Supported STT extensions based on Gnani STT SDK
SUPPORTED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".ogg", ".flac", ".aac", ".m4a"}

# Default STT / TTS configuration
DEFAULT_STT_LANGUAGE = "en-IN"
DEFAULT_TTS_LANGUAGE = "en-IN"
DEFAULT_TTS_VOICE = "Kaveri"
DEFAULT_TTS_MODEL = "timbre-v2.5"


class GnaniVoiceError(Exception):
    """Base exception for Gnani voice integration errors."""
    pass


class GnaniSTT:
    """
    Wrapper around Gnani.ai Speech-to-Text SDK.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        language_code: str = DEFAULT_STT_LANGUAGE,
        format: str = "transcribe",
        client: Any = None,
    ):
        self.api_key = api_key or os.getenv("GNANI_API_KEY")
        self.language_code = language_code
        self.format = format
        self._client = client

    def _get_client(self):
        if self._client is not None:
            return self._client
        if not self.api_key:
            raise GnaniVoiceError(
                "GNANI_API_KEY is not configured in the environment. "
                "Please set GNANI_API_KEY or inject a mock client."
            )
        try:
            from gnani.stt import GnaniSTTClient
            self._client = GnaniSTTClient(api_key=self.api_key)
            return self._client
        except ImportError as exc:
            raise GnaniVoiceError(
                "gnani-vachana package is not installed. Run: pip install gnani-vachana"
            ) from exc
        except Exception as exc:
            raise GnaniVoiceError(f"Failed to initialize GnaniSTTClient: {exc.__class__.__name__}") from exc

    def transcribe(self, audio_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Transcribe a local audio file into text using Gnani STT.

        Parameters
        ----------
        audio_path : str | Path
            Path to the audio file (.wav, .mp3, .ogg, .flac, .aac, .m4a).

        Returns
        -------
        dict
            Dict containing 'transcript', 'request_id', and 'raw_response'.
        """
        path = Path(audio_path)

        # 1. Validate file exists
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {path}")

        # 2. Validate file is not a directory
        if not path.is_file():
            raise ValueError(f"Path is not a regular file: {path}")

        # 3. Validate supported extension
        ext = path.suffix.lower()
        if ext not in SUPPORTED_AUDIO_EXTENSIONS:
            raise ValueError(
                f"Unsupported audio format '{ext}'. Gnani STT supports: "
                f"{', '.join(sorted(SUPPORTED_AUDIO_EXTENSIONS))}"
            )

        # 4. Validate non-empty file
        if path.stat().st_size == 0:
            raise ValueError(f"Audio file is empty (0 bytes): {path}")

        client = self._get_client()

        try:
            res = client.transcribe(
                str(path),
                language_code=self.language_code,
                format=self.format,
            )
        except Exception as exc:
            # Re-raise with clean error message without exposing credentials
            raise GnaniVoiceError(f"Gnani STT transcription failed ({exc.__class__.__name__}): {exc}") from exc

        # 5. Extract and validate transcript
        if not isinstance(res, dict):
            raise GnaniVoiceError(f"Unexpected response type from Gnani STT: {type(res).__name__}")

        transcript = res.get("transcript") or res.get("text") or ""
        clean_text = str(transcript).strip()

        if not clean_text:
            raise ValueError("Gnani STT returned an empty transcription for the audio input.")

        return {
            "transcript": clean_text,
            "request_id": res.get("request_id"),
            "raw_response": res,
        }


class GnaniTTS:
    """
    Wrapper around Gnani.ai Text-to-Speech SDK.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        voice: str = DEFAULT_TTS_VOICE,
        model: str = DEFAULT_TTS_MODEL,
        language: str = DEFAULT_TTS_LANGUAGE,
        client: Any = None,
    ):
        self.api_key = api_key or os.getenv("GNANI_API_KEY")
        self.voice = voice
        self.model = model
        self.language = language
        self._client = client

    def _get_client(self):
        if self._client is not None:
            return self._client
        if not self.api_key:
            raise GnaniVoiceError(
                "GNANI_API_KEY is not configured in the environment. "
                "Please set GNANI_API_KEY or inject a mock client."
            )
        try:
            from gnani.tts import GnaniTTSClient
            self._client = GnaniTTSClient(api_key=self.api_key)
            return self._client
        except ImportError as exc:
            raise GnaniVoiceError(
                "gnani-vachana package is not installed. Run: pip install gnani-vachana"
            ) from exc
        except Exception as exc:
            raise GnaniVoiceError(f"Failed to initialize GnaniTTSClient: {exc.__class__.__name__}") from exc

    def synthesize(self, text: str, output_file: Optional[Union[str, Path]] = None) -> bytes:
        """
        Convert customer-facing text into speech using Gnani TTS.

        Parameters
        ----------
        text : str
            The customer-facing text to speak.
        output_file : str | Path, optional
            Local path to save the generated audio file (.wav).

        Returns
        -------
        bytes
            Synthesized audio bytes.
        """
        clean_text = (text or "").strip()
        if not clean_text:
            raise ValueError("Text for speech synthesis cannot be empty.")

        client = self._get_client()

        out_path = Path(output_file) if output_file else None
        if out_path:
            out_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            audio_bytes = client.synthesize(
                clean_text,
                voice=self.voice,
                model=self.model,
                language=self.language,
                output_file=str(out_path) if out_path else None,
            )
        except Exception as exc:
            raise GnaniVoiceError(f"Gnani TTS synthesis failed ({exc.__class__.__name__}): {exc}") from exc

        if not audio_bytes or len(audio_bytes) == 0:
            # Check if file was written directly by SDK
            if out_path and out_path.exists() and out_path.stat().st_size > 0:
                audio_bytes = out_path.read_bytes()
            else:
                raise ValueError("Gnani TTS returned empty audio data.")

        # Ensure output file is persisted if passed
        if out_path:
            if not out_path.exists() or out_path.stat().st_size == 0:
                out_path.write_bytes(audio_bytes)

        return audio_bytes


# ----------------------------------------------------
# Convenience Helper Functions
# ----------------------------------------------------

def transcribe_audio(
    audio_path: Union[str, Path],
    api_key: Optional[str] = None,
    language_code: str = DEFAULT_STT_LANGUAGE,
    client: Any = None,
) -> str:
    """
    Transcribe a local audio file to text.
    Returns the recognized transcript string.
    """
    stt = GnaniSTT(api_key=api_key, language_code=language_code, client=client)
    res = stt.transcribe(audio_path)
    return res["transcript"]


def synthesize_speech(
    text: str,
    output_path: Union[str, Path],
    api_key: Optional[str] = None,
    voice: str = DEFAULT_TTS_VOICE,
    model: str = DEFAULT_TTS_MODEL,
    language: str = DEFAULT_TTS_LANGUAGE,
    client: Any = None,
) -> Path:
    """
    Synthesize text into speech and save to output_path.
    Returns the Path to the generated audio file.
    """
    tts = GnaniTTS(api_key=api_key, voice=voice, model=model, language=language, client=client)
    dest = Path(output_path)
    tts.synthesize(text, output_file=dest)
    return dest
