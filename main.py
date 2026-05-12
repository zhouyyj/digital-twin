"""Mirror Image — terminal session with a streamed mirror persona."""

from __future__ import annotations

import sys

from colorama import Fore, Style, init as colorama_init
from openai import OpenAI

from core.config import get_openai_api_key, get_openai_base_url, get_openai_model, load_env

SYSTEM_PROMPT = (
    "你是我在镜子里的克隆体，说话极其克制、一针见血，习惯用提问来剖析我的思维逻辑。"
)

# System chrome: dim green; mirror clone reply: cyan
STYLE_SYSTEM = Fore.GREEN + Style.DIM
STYLE_CLONE = Fore.CYAN
STYLE_RESET = Style.RESET_ALL
STYLE_DIM = Style.DIM


def _print_banner() -> None:
    title = f"{STYLE_SYSTEM}Mirror Image{STYLE_RESET}"
    sub = f"{Style.DIM}数字孪生与认知推演 · Phase 0{STYLE_RESET}"
    print(f"\n{title}\n{sub}\n")
    print(
        f"{STYLE_SYSTEM}输入你的问题，"
        f"{STYLE_DIM}exit / quit / Ctrl+D 结束{STYLE_RESET}\n"
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


def main() -> int:
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

        messages.append({"role": "user", "content": user_line})

        try:
            print(f"{STYLE_CLONE}镜 › {STYLE_RESET}", end="", flush=True)
            reply = _stream_reply(client, model, messages)
        except Exception as exc:
            messages.pop()
            print(
                f"{Fore.RED}[API 错误] {exc}{Style.RESET_ALL}",
                file=sys.stderr,
            )
            continue

        messages.append({"role": "assistant", "content": reply})

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
