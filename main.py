"""Home Repair Chatbot — interactive CLI entrypoint."""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

from graph import build_graph
from graph.state import ChatState


BANNER = """
╔══════════════════════════════════════════╗
║       Home Repair Chatbot                ║
║  Describe a repair problem and get help  ║
║  Type 'quit' or 'exit' to leave          ║
╚══════════════════════════════════════════╝
"""


def main() -> int:
    load_dotenv(Path(__file__).resolve().parent / ".env")
    graph = build_graph()

    state: ChatState = {
        "messages": [],
        "last_user_message": "",
        "assistant_reply": "",
        "awaiting": None,
        "email": None,
        "user_id": None,
        "user_info": None,
        "hasActiveComponent": False,
        "hasActiveProblem": False,
        "active_component_id": None,
        "active_component": None,
        "latest_search_question": None,
        "latest_search_result": None,
        "tool_recommendations": [],
        "tools_selected": [],
        "tools_presented": False,
        "initializer_complete": False,
        "from_check_result": False,
        "pending_component": None,
        "candidate_component": None,
        "pending_new_user": None,
        "pending_problem_desc": None,
        "done": False,
    }

    print(BANNER)

    # Kick off initializer (asks for email)
    state = graph.invoke(state)
    print(f"\nBot: {state.get('assistant_reply', '')}\n")

    while not state.get("done"):
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBot: Goodbye!")
            return 0

        if user_input.lower() in {"quit", "exit", "q"}:
            print("Bot: Goodbye!")
            return 0

        state = {
            **state,
            "last_user_message": user_input,
            "assistant_reply": "",
        }
        state = graph.invoke(state)
        reply = state.get("assistant_reply") or ""
        if reply:
            print(f"\nBot: {reply}\n")

        if state.get("done"):
            break

    return 0


if __name__ == "__main__":
    sys.exit(main())
