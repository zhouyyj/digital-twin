"""Digital Twin — terminal session with a streamed persona."""

from __future__ import annotations

import sys

from colorama import Fore, Style, init as colorama_init
from openai import OpenAI

from core.config import get_openai_api_key, get_openai_base_url, get_openai_model, load_env
from core.feeder import PersonalFeeder
from core.memory_manager import MemoryManager
from core.sandbox import CognitiveSandbox
from core.state_machine import (
    UserState,
    is_deduction_request,
)
from core.twin_model import TwinModel

SYSTEM_PROMPT = (
    "You are my evidence-bound digital twin. Speak with restraint and precision. "
    "Separate what is observed, inferred, and unknown. Use questions to cut into "
    "my thinking; never replace uncertainty with generic advice. Reply in English."
)

# System chrome: dim green; mirror clone reply: cyan
STYLE_SYSTEM = Fore.GREEN + Style.DIM
STYLE_CLONE = Fore.CYAN
STYLE_RESET = Style.RESET_ALL
STYLE_DIM = Style.DIM


def _ensure_utf8_stdio() -> None:
    """Avoid UnicodeEncodeError when the terminal locale forces ascii on stdout/stderr."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError, AttributeError):
                pass


def _print_banner() -> None:
    title = f"{STYLE_SYSTEM}Digital Twin{STYLE_RESET}"
    sub = f"{Style.DIM}Digital twin and cognitive sandbox · Phase 4 (watering){STYLE_RESET}"
    print(f"\n{title}\n{sub}\n")
    print(
        f"{STYLE_SYSTEM}Ask something. "
        f"{STYLE_DIM}exit / quit / Ctrl+D to leave · /model · /board · /simulate · "
        f"/water <path|note:…> · /memory{STYLE_RESET}\n"
    )


def _stream_reply(client: OpenAI, model: str, messages: list[dict]) -> str:
    print(f"{STYLE_CLONE}", end="", flush=True)
    buffer: list[str] = []
    try:
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
        )
        for event in stream:
            if not event.choices:
                continue
            delta = event.choices[0].delta
            if delta and delta.content:
                piece = delta.content
                buffer.append(piece)
                print(piece, end="", flush=True)
    finally:
        print(STYLE_RESET, flush=True)
    return "".join(buffer)


def _memory_augmented_user_content(user_line: str, memory: MemoryManager) -> str:
    hits = memory.search_relevant_events(user_line, limit=5)
    if not hits:
        return user_line
    lines: list[str] = []
    for i, h in enumerate(hits, start=1):
        ts = h.get("timestamp", "")
        et = h.get("event_type", "")
        src = h.get("source", "")
        body = h.get("text", "")
        src_bit = f" · {src}" if src else ""
        lines.append(f"[{i}] {ts} | {et}{src_bit}\n{body}")
    block = "\n\n".join(lines)
    return (
        "Here are related past events and watered material (ISO timestamps) "
        "for you to use. Ignore anything that does not bear on this turn.\n\n"
        f"{block}\n\n"
        "---\n\n"
        f"[Current input]\n{user_line}"
    )


def main() -> int:
    _ensure_utf8_stdio()
    colorama_init(autoreset=False)
    load_env()

    try:
        api_key = get_openai_api_key()
    except RuntimeError as e:
        print(f"{Fore.RED}{e}{Style.RESET_ALL}", file=sys.stderr)
        return 1

    model = get_openai_model()
    base_url = get_openai_base_url()
    client = OpenAI(api_key=api_key, base_url=base_url)
    memory = MemoryManager(client)
    user_state = UserState.load()
    twin_model = TwinModel(client, memory, model=model)
    sandbox = CognitiveSandbox(client, memory, user_state, model, twin_model)
    feeder = PersonalFeeder(client, memory, model=model)

    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]

    _print_banner()

    while True:
        try:
            user_line = input(f"{STYLE_SYSTEM}you › {STYLE_RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{STYLE_SYSTEM}Session ended.{STYLE_RESET}")
            break

        if not user_line:
            continue
        if user_line.lower() in {"exit", "quit", ":q"}:
            print(f"{STYLE_SYSTEM}Session ended.{STYLE_RESET}")
            break

        if user_line in {"/model", "/state"}:
            profile = twin_model.load()
            print(f"\n{STYLE_SYSTEM}── Twin model ──{STYLE_RESET}")
            print(f"{STYLE_CLONE}{profile.get('summary', '')}{STYLE_RESET}")
            print(
                f"{STYLE_SYSTEM}confidence={float(profile.get('confidence', 0)):.0%} · "
                f"observations={profile.get('observations', 0)} · "
                f"unknowns={len(profile.get('unknowns') or [])}{STYLE_RESET}\n"
            )
            continue

        if user_line == "/memory":
            print(
                f"{STYLE_SYSTEM}Memory store: {memory.count_events()} events"
                f" (chat + watered material){STYLE_RESET}\n"
            )
            continue

        if user_line.startswith("/water") or user_line.startswith("/feed"):
            if user_line.startswith("/water"):
                target = user_line.removeprefix("/water").strip()
            else:
                target = user_line.removeprefix("/feed").strip()
            try:
                results = feeder.water(target)
            except Exception as exc:
                print(
                    f"{Fore.RED}[watering failed] {exc}{Style.RESET_ALL}",
                    file=sys.stderr,
                )
                continue
            total = sum(r.chunks for r in results)
            twin_model.refresh(reason="water:cli")
            print(
                f"{STYLE_SYSTEM}Watered: {len(results)} file(s) / {total} chunks into memory."
                f"{STYLE_RESET}\n"
            )
            continue

        if user_line.startswith("/board"):
            dilemma = user_line.removeprefix("/board").strip()
            try:
                sandbox.run_board(dilemma)
            except Exception as exc:
                print(
                    f"{Fore.RED}[sandbox /board error] {exc}{Style.RESET_ALL}",
                    file=sys.stderr,
                )
            continue

        if user_line.startswith("/simulate"):
            choice = user_line.removeprefix("/simulate").strip()
            try:
                sandbox.run_simulate(choice)
            except Exception as exc:
                print(
                    f"{Fore.RED}[sandbox /simulate error] {exc}{Style.RESET_ALL}",
                    file=sys.stderr,
                )
            continue

        user_for_model = (
            "[Durable twin model]\n"
            f"{twin_model.compact_context()}\n\n"
            + _memory_augmented_user_content(user_line, memory)
        )
        if is_deduction_request(user_line):
            user_for_model += (
                "\n\nFor this choice, separate observed constraints, inferred pressure, and unknowns. "
                "Use counterfactual worlds when uncertainty changes the outcome. Do not invent exact meters."
            )

        turn_messages = [*messages, {"role": "user", "content": user_for_model}]

        try:
            print(f"{STYLE_CLONE}twin › {STYLE_RESET}", end="", flush=True)
            reply = _stream_reply(client, model, turn_messages)
        except Exception as exc:
            print(
                f"{Fore.RED}[API error] {exc}{Style.RESET_ALL}",
                file=sys.stderr,
            )
            continue

        messages.append({"role": "user", "content": user_line})
        messages.append({"role": "assistant", "content": reply})

        try:
            memory.add_event(user_line, "User_Thought")
            memory.add_event(reply, "AI_Intervention")
        except Exception as exc:
            print(
                f"{Fore.RED}[memory write failed] {exc}{Style.RESET_ALL}",
                file=sys.stderr,
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
