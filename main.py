"""Mirror Image — terminal session with a streamed mirror persona."""

from __future__ import annotations

import sys

from colorama import Fore, Style, init as colorama_init
from openai import OpenAI

from core.config import get_openai_api_key, get_openai_base_url, get_openai_model, load_env
from core.feeder import PersonalFeeder
from core.memory_manager import MemoryManager
from core.sandbox import CognitiveSandbox
from core.state_machine import (
    PHYSICAL_ALERT_CN,
    UserState,
    deduction_instruction_block,
    evaluate_deduction_reply,
    is_deduction_request,
)

SYSTEM_PROMPT = (
    "你是我在镜子里的克隆体，说话极其克制、一针见血，习惯用提问来剖析我的思维逻辑。"
    "你可以调用用户主动浇灌进记忆的日记、文档与图像描述；不要假装看见未被提供的私料。"
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
    title = f"{STYLE_SYSTEM}Mirror Image{STYLE_RESET}"
    sub = f"{Style.DIM}数字孪生与认知推演 · Phase 4（浇灌）{STYLE_RESET}"
    print(f"\n{title}\n{sub}\n")
    print(
        f"{STYLE_SYSTEM}输入你的问题，"
        f"{STYLE_DIM}exit / quit / Ctrl+D 结束 · /state · /board · /simulate · "
        f"/water <路径|note:…> · /memory{STYLE_RESET}\n"
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


def _collect_stream_reply(client: OpenAI, model: str, messages: list[dict]) -> str:
    """Stream to memory only (for deduction paths that must be validated before display)."""
    buffer: list[str] = []
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
            buffer.append(delta.content)
    return "".join(buffer)


def _print_user_state(state: UserState) -> None:
    print(f"\n{STYLE_SYSTEM}── 物理残余 (/state) ──{STYLE_RESET}")
    print(f"{STYLE_SYSTEM}capital       : {state.capital:.2f}{STYLE_RESET}")
    print(f"{STYLE_SYSTEM}energy        : {state.energy:.2f}{STYLE_RESET}")
    print(f"{STYLE_SYSTEM}entropy_rate  : {state.entropy_rate:.2f}{STYLE_RESET}\n")


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
        "以下是与当前输入相关的历史事件与浇灌材料（含 ISO 时间戳），供你对照推演；"
        "忽略与当下无关的信息。\n\n"
        f"{block}\n\n"
        "---\n\n"
        f"【当前输入】\n{user_line}"
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
    sandbox = CognitiveSandbox(client, memory, user_state, model)
    feeder = PersonalFeeder(client, memory, model=model)

    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]

    _print_banner()

    while True:
        try:
            user_line = input(f"{STYLE_SYSTEM}你 › {STYLE_RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{STYLE_SYSTEM}会话结束。{STYLE_RESET}")
            break

        if not user_line:
            continue
        if user_line.lower() in {"exit", "quit", ":q"}:
            print(f"{STYLE_SYSTEM}会话结束。{STYLE_RESET}")
            break

        if user_line == "/state":
            _print_user_state(user_state)
            continue

        if user_line == "/memory":
            print(
                f"{STYLE_SYSTEM}记忆库存：{memory.count_events()} 条事件"
                f"（对话 + 浇灌材料）{STYLE_RESET}\n"
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
                    f"{Fore.RED}[浇灌失败] {exc}{Style.RESET_ALL}",
                    file=sys.stderr,
                )
                continue
            total = sum(r.chunks for r in results)
            print(
                f"{STYLE_SYSTEM}浇灌完成：{len(results)} 个文件 / 共 {total} 块写入记忆。"
                f"{STYLE_RESET}\n"
            )
            continue

        if user_line.startswith("/board"):
            dilemma = user_line.removeprefix("/board").strip()
            try:
                sandbox.run_board(dilemma)
            except Exception as exc:
                print(
                    f"{Fore.RED}[沙盒 /board 错误] {exc}{Style.RESET_ALL}",
                    file=sys.stderr,
                )
            continue

        if user_line.startswith("/simulate"):
            choice = user_line.removeprefix("/simulate").strip()
            try:
                sandbox.run_simulate(choice)
            except Exception as exc:
                print(
                    f"{Fore.RED}[沙盒 /simulate 错误] {exc}{Style.RESET_ALL}",
                    file=sys.stderr,
                )
            continue

        deduction_mode = is_deduction_request(user_line)
        user_for_model = _memory_augmented_user_content(user_line, memory)
        if deduction_mode:
            user_for_model = user_for_model + "\n\n" + deduction_instruction_block(user_state)

        turn_messages = [*messages, {"role": "user", "content": user_for_model}]

        try:
            print(f"{STYLE_CLONE}镜 › {STYLE_RESET}", end="", flush=True)
            if deduction_mode:
                reply_full = _collect_stream_reply(client, model, turn_messages)
                display, outcome = evaluate_deduction_reply(user_state, reply_full)
                if outcome == "intercepted":
                    print(
                        f"{Fore.RED}{PHYSICAL_ALERT_CN}{Style.RESET_ALL}\n",
                        flush=True,
                    )
                    continue
                if outcome == "no_json":
                    print(
                        f"{Fore.YELLOW}[系统] 未解析到有效的状态消耗 JSON，物理数值未变更。"
                        f"{Style.RESET_ALL}",
                        file=sys.stderr,
                    )
                print(f"{STYLE_CLONE}{display}{STYLE_RESET}\n", flush=True)
                reply = display
            else:
                reply = _stream_reply(client, model, turn_messages)
        except Exception as exc:
            print(
                f"{Fore.RED}[API 错误] {exc}{Style.RESET_ALL}",
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
                f"{Fore.RED}[记忆写入失败] {exc}{Style.RESET_ALL}",
                file=sys.stderr,
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
