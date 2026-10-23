"""
ZentroMart VoiceOps — Application Entry Point.

Provides text and voice handling interfaces for customer interactions.
"""

from pathlib import Path
from typing import Dict, Any, Optional, Union
from src.conversation import ZentroMartConversation, _session_manager
from src.voice import transcribe_audio, synthesize_speech


def handle_message(message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Handle an incoming customer text message for a session.
    Returns structured response dict.
    """
    agent = ZentroMartConversation(session_id=session_id)
    return agent.respond(message)


def handle_voice_message(
    audio_path: Union[str, Path],
    output_audio_path: Optional[Union[str, Path]] = None,
    session_id: Optional[str] = None,
    stt_client: Any = None,
    tts_client: Any = None,
) -> Dict[str, Any]:
    """
    Handle an incoming customer voice message:
    1. Transcribe audio with Gnani STT
    2. Process recognized text through ZentroMartConversation
    3. Synthesize customer answer to speech with Gnani TTS
    """
    transcript = transcribe_audio(audio_path, client=stt_client)
    agent = ZentroMartConversation(session_id=session_id)
    response = agent.respond(transcript)

    output_audio = None
    if output_audio_path:
        out_path = Path(output_audio_path)
        synthesize_speech(response["answer"], output_path=out_path, client=tts_client)
        output_audio = str(out_path)

    return {
        "transcribed_message": transcript,
        "response": response,
        "output_audio": output_audio,
    }


def reset_session(session_id: str):
    """Reset a conversation session."""
    _session_manager.reset_session(session_id)


if __name__ == "__main__":
    from run import interactive_mode
    interactive_mode()
