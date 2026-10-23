"""
ZentroMart VoiceOps — End-to-End Batch Audio Processing Runner.

Processes a folder of customer audio messages through:
1. Gnani STT (speech-to-text) -> transcript
2. ZentroMart Text Agent (ZentroMartConversation.respond) -> grounded response & evidence
3. Gnani TTS (text-to-speech) -> synthesized spoken reply

Output structure:
<output_dir>/
  audio/           -> synthesized response audio files (.wav)
  transcripts/     -> recognized input user text (.txt)
  responses/       -> customer-facing response text (.txt)
  evidence/        -> response metadata and retrieved chunks (.json)
  run_summary.json -> batch processing summary
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from uuid import uuid4

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.conversation import ZentroMartConversation
from src.voice import (
    GnaniSTT,
    GnaniTTS,
    SUPPORTED_AUDIO_EXTENSIONS,
    GnaniVoiceError,
)


def sanitize_filename(name: str) -> str:
    """Sanitize filename to avoid path traversal or illegal characters."""
    base = Path(name).stem
    cleaned = re.sub(r"[^A-Za-z0-9_\-\.]", "_", base)
    return cleaned.strip("_") or "audio_item"


def process_audio_batch(
    input_dir: Union[str, Path],
    output_dir: Union[str, Path],
    session_id: Optional[str] = None,
    separate_sessions: bool = False,
    stt_client: Any = None,
    tts_client: Any = None,
    conversation_agent: Optional[ZentroMartConversation] = None,
) -> Dict[str, Any]:
    """
    Process an entire folder of audio files through STT -> Agent -> TTS.

    Parameters
    ----------
    input_dir : str | Path
        Directory containing input audio files.
    output_dir : str | Path
        Directory where outputs are stored.
    session_id : str, optional
        Explicit session identifier for the run.
    separate_sessions : bool
        If True, each audio file is processed in its own independent session.
    stt_client : Any, optional
        Custom or mock STT client.
    tts_client : Any, optional
        Custom or mock TTS client.
    conversation_agent : ZentroMartConversation, optional
        Pre-configured conversation agent instance.

    Returns
    -------
    dict
        Summary dictionary with counts, file statuses, and output paths.
    """
    inp_path = Path(input_dir)
    out_path = Path(output_dir)

    if not inp_path.exists():
        raise FileNotFoundError(f"Input directory does not exist: {inp_path}")
    if not inp_path.is_dir():
        raise NotADirectoryError(f"Input path is not a directory: {inp_path}")

    # Create organized output directories
    audio_out_dir = out_path / "audio"
    transcripts_out_dir = out_path / "transcripts"
    responses_out_dir = out_path / "responses"
    evidence_out_dir = out_path / "evidence"

    for d in (audio_out_dir, transcripts_out_dir, responses_out_dir, evidence_out_dir):
        d.mkdir(parents=True, exist_ok=True)

    # Discover and sort supported audio files deterministically
    audio_files = [
        p for p in inp_path.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS
    ]
    audio_files.sort(key=lambda p: p.name)

    base_session_id = session_id or f"voice_run_{uuid4().hex[:10]}"
    shared_agent = conversation_agent or ZentroMartConversation(session_id=base_session_id)

    stt = GnaniSTT(client=stt_client)
    tts = GnaniTTS(client=tts_client)

    results: List[Dict[str, Any]] = []
    successful_count = 0
    failed_count = 0

    print(f"Discovered {len(audio_files)} audio file(s) in '{inp_path}'. Processing...")

    for file_path in audio_files:
        stem = sanitize_filename(file_path.name)
        file_summary: Dict[str, Any] = {
            "input_filename": file_path.name,
            "status": "pending",
            "transcribed_message": None,
            "agent_answer": None,
            "agent_decision": None,
            "sources": [],
            "turn": None,
            "output_audio": None,
            "error": None,
        }

        # Determine agent/session for this file
        if separate_sessions:
            current_session_id = f"{base_session_id}_{stem}"
            current_agent = ZentroMartConversation(session_id=current_session_id)
        else:
            current_agent = shared_agent

        try:
            # 1. Speech-to-Text
            stt_res = stt.transcribe(file_path)
            transcript = stt_res["transcript"]
            file_summary["transcribed_message"] = transcript

            # Persist transcript
            transcript_file = transcripts_out_dir / f"{stem}.txt"
            transcript_file.write_text(transcript, encoding="utf-8")

            # 2. Text Agent Response
            response = current_agent.respond(transcript)
            answer = response.get("answer", "")
            decision = response.get("decision", "answer")
            sources = response.get("sources", [])
            evidence = response.get("evidence", [])
            turn = response.get("turn", 1)

            file_summary["agent_answer"] = answer
            file_summary["agent_decision"] = decision
            file_summary["sources"] = sources
            file_summary["turn"] = turn

            # Persist response text
            response_file = responses_out_dir / f"{stem}.txt"
            response_file.write_text(answer, encoding="utf-8")

            # 3. Text-to-Speech
            out_audio_file = audio_out_dir / f"{stem}.wav"
            tts.synthesize(answer, output_file=out_audio_file)
            file_summary["output_audio"] = str(out_audio_file.name)

            # 4. Persist Evidence & Response Metadata
            # Redact any customer PII from tool results
            sanitized_tools = []
            for tr in response.get("tool_results", []):
                safe_tr = {k: v for k, v in tr.items() if k not in ("phone", "email")}
                sanitized_tools.append(safe_tr)

            evidence_data = {
                "input_filename": file_path.name,
                "transcribed_message": transcript,
                "agent_answer": answer,
                "agent_decision": decision,
                "sources": sources,
                "evidence": evidence,
                "session_id": current_agent.session_id,
                "turn": turn,
                "tool_results": sanitized_tools,
                "created_ticket": response.get("created_ticket"),
                "output_audio": str(out_audio_file.name),
                "status": "success",
            }
            evidence_file = evidence_out_dir / f"{stem}.json"
            evidence_file.write_text(json.dumps(evidence_data, indent=2, ensure_ascii=False), encoding="utf-8")

            file_summary["status"] = "success"
            successful_count += 1
            print(f"  [OK] {file_path.name} -> {decision.upper()}: '{answer[:60]}...'")

        except Exception as exc:
            failed_count += 1
            err_msg = f"{exc.__class__.__name__}: {str(exc)}"
            file_summary["status"] = "failed"
            file_summary["error"] = err_msg

            # Save error record
            err_record = {
                "input_filename": file_path.name,
                "status": "failed",
                "error": err_msg,
            }
            err_file = evidence_out_dir / f"{stem}_error.json"
            err_file.write_text(json.dumps(err_record, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"  [FAIL] {file_path.name} -> {err_msg}")

        results.append(file_summary)

    # 5. Persist run summary
    summary = {
        "input_directory": str(inp_path),
        "output_directory": str(out_path),
        "session_id": base_session_id,
        "separate_sessions": separate_sessions,
        "total_files": len(audio_files),
        "successful": successful_count,
        "failed": failed_count,
        "files": results,
    }
    summary_file = out_path / "run_summary.json"
    summary_file.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n" + "=" * 60)
    print(f"Batch Processing Completed:")
    print(f"  Total: {len(audio_files)} | Successful: {successful_count} | Failed: {failed_count}")
    print(f"  Summary saved to: {summary_file}")
    print("=" * 60)

    return summary


def main():
    parser = argparse.ArgumentParser(description="ZentroMart VoiceOps Audio Batch Runner")
    parser.add_argument("--input-dir", "-i", type=str, required=True, help="Directory containing audio input files")
    parser.add_argument("--output-dir", "-o", type=str, required=True, help="Directory for output audio, transcripts, and evidence")
    parser.add_argument("--session-id", "-s", type=str, default=None, help="Explicit conversation session ID")
    parser.add_argument("--separate-sessions", action="store_true", help="Use a separate session per audio file")
    args = parser.parse_args()

    process_audio_batch(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        session_id=args.session_id,
        separate_sessions=args.separate_sessions,
    )


if __name__ == "__main__":
    main()
