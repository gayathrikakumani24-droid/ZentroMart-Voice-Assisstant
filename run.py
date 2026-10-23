"""
ZentroMart VoiceOps — Unified CLI Runner.

Supports:
1. Audio Batch Processing:
   python run.py --input-dir samples/input --output-dir outputs/voice_run
2. Interactive Text Chat:
   python run.py --interactive
3. Single Text Query:
   python run.py --query "How fast are refunds to the ZentroMart Wallet?"
"""

import argparse
import sys
from src.conversation import ZentroMartConversation
from run_audio import process_audio_batch


def interactive_mode():
    print("=" * 65)
    print("ZentroMart VoiceOps Support Agent (Reference Date: 20 Oct 2026)")
    print("Type 'exit' or 'quit' to end. Type 'reset' to clear session.")
    print("=" * 65)

    agent = ZentroMartConversation()
    while True:
        try:
            user_input = input("\nCustomer: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit"):
                print("Session ended.")
                break

            response = agent.respond(user_input)
            print(f"\nAssistant [{response['decision'].upper()}]: {response['answer']}")
            if response["sources"]:
                print(f"  Sources: {', '.join(response['sources'])}")
            if response["created_ticket"]:
                print(f"  Ticket Created: {response['created_ticket']['ticket_id']}")
        except (KeyboardInterrupt, EOFError):
            print("\nSession ended.")
            break


def single_query(query: str):
    agent = ZentroMartConversation()
    response = agent.respond(query)
    print(f"Query: {query}")
    print(f"Decision: {response['decision']}")
    print(f"Answer: {response['answer']}")
    print(f"Sources: {', '.join(response['sources'])}")


def main():
    parser = argparse.ArgumentParser(description="ZentroMart Support Agent")
    parser.add_argument("--interactive", "-i", action="store_true", help="Start interactive chat")
    parser.add_argument("--query", "-q", type=str, help="Run a single question query")
    parser.add_argument("--input-dir", type=str, help="Input directory containing audio files for batch processing")
    parser.add_argument("--output-dir", type=str, help="Output directory for audio batch processing")
    parser.add_argument("--session-id", type=str, default=None, help="Explicit conversation session ID")
    parser.add_argument("--separate-sessions", action="store_true", help="Use a separate session per audio file")
    args = parser.parse_args()

    if args.input_dir and args.output_dir:
        process_audio_batch(
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            session_id=args.session_id,
            separate_sessions=args.separate_sessions,
        )
    elif args.query:
        single_query(args.query)
    elif args.interactive:
        interactive_mode()
    else:
        # Default to interactive if no flags passed
        interactive_mode()


if __name__ == "__main__":
    main()
