"""Phase 3 — cognitive board + stepped month simulation."""

from __future__ import annotations

import random
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable

from colorama import Fore, Style
from openai import OpenAI

from core.memory_manager import MemoryManager
from core.state_machine import (
    PHYSICAL_ALERT,
    UserState,
    deduction_instruction_block,
    evaluate_deduction_reply,
)

PrintFn = Callable[..., None]

_HDR = Fore.GREEN + Style.DIM
_BODY = Fore.CYAN
_RST = Style.RESET_ALL
_WARN = Fore.YELLOW


@dataclass(frozen=True)
class _Persona:
    label: str
    memory_bias: str
    temperature: float
    system: str


_PERSONAS: tuple[_Persona, ...] = (
    _Persona(
        label="Radical breaker",
        memory_bias="risk leverage asymmetric offense delay",
        temperature=0.92,
        system=(
            "You are the Radical breaker on the board: bet on asymmetric upside, hate stalling. "
            "Speak in sharp short sentences. Overturn default assumptions. Reply in English."
        ),
    ),
    _Persona(
        label="Rational analyst",
        memory_bias="risk return probability cashflow stability data",
        temperature=0.35,
        system=(
            "You are the Rational analyst: take options apart with expected value and testable premises. "
            "Name key uncertainties and the worst case. No empty pep talk. Reply in English."
        ),
    ),
    _Persona(
        label="Deep reflector",
        memory_bias="meaning fear identity regret long-term motive",
        temperature=0.62,
        system=(
            "You are the Deep reflector: ask who is afraid of what, and the second-order cost. "
            "Map the bind onto self-story and ethics. Restrained, a little cutting. Reply in English."
        ),
    ),
)

_FRICTION_EVENTS: tuple[dict[str, str | float], ...] = (
    {
        "label": "A key machine breaks; repair and downtime eat cash",
        "capital_delta": -10.0,
        "energy_delta": -7.0,
        "entropy_rate_delta": 0.02,
    },
    {
        "label": "A partner misses a payment; cashflow tightens",
        "capital_delta": -14.0,
        "energy_delta": -6.0,
        "entropy_rate_delta": 0.04,
    },
    {
        "label": "A reputation shock; defending it costs bandwidth",
        "capital_delta": -4.0,
        "energy_delta": -11.0,
        "entropy_rate_delta": 0.05,
    },
    {
        "label": "A core person leaves; the team has to relearn itself",
        "capital_delta": -6.0,
        "energy_delta": -12.0,
        "entropy_rate_delta": 0.03,
    },
    {
        "label": "A compliance check; unexpected spend",
        "capital_delta": -9.0,
        "energy_delta": -5.0,
        "entropy_rate_delta": 0.02,
    },
)


def _format_memory_hits(hits: list[dict]) -> str:
    if not hits:
        return "(No nearby memory yet.)"
    lines: list[str] = []
    for i, h in enumerate(hits, start=1):
        ts = h.get("timestamp", "")
        et = h.get("event_type", "")
        body = h.get("text", "")
        lines.append(f"[{i}] {ts} | {et}\n{body}")
    return "Memory that bears on this seat:\n\n" + "\n\n".join(lines)


def _chat_once(
    client: OpenAI,
    model: str,
    messages: list[dict],
    *,
    temperature: float,
    max_tokens: int = 1400,
) -> str:
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=False,
    )
    msg = resp.choices[0].message
    return (msg.content or "").strip()


def _apply_friction_scaled(state: UserState, ev: dict[str, str | float]) -> tuple[bool, str]:
    """Apply friction without driving energy negative; scale down if needed."""
    label = str(ev["label"])
    for scale in (1.0, 0.55, 0.3):
        cd = float(ev["capital_delta"]) * scale
        ed = float(ev["energy_delta"]) * scale
        er = float(ev["entropy_rate_delta"]) * scale
        if state.preview_energy_after(ed) < 0:
            continue
        if state.apply_deltas(cd, ed, er):
            suffix = f" (friction ×{scale:g})" if scale < 1.0 else ""
            return True, f"{label}{suffix}"
    return False, label


def _roll_friction(state: UserState) -> tuple[str | None, str]:
    """
    Maybe fire an outside shock, using entropy_rate.
    Returns (friction line if it landed, human-readable roll note).
    """
    p = min(0.9, 0.08 + float(state.entropy_rate) * 1.15)
    roll = random.random()
    summary = f"p={p:.2f}, roll={roll:.3f}, entropy_rate={state.entropy_rate:.2f}"
    if roll >= p:
        return None, summary
    ev = random.choice(_FRICTION_EVENTS)
    ok, desc = _apply_friction_scaled(state, ev)
    if not ok:
        return None, summary + " → friction blocked by the physical ceiling"
    return desc, summary


class CognitiveSandbox:
    """Board of minds (parallel views + rebuttal) and stepped monthly simulation."""

    def __init__(
        self,
        client: OpenAI,
        memory: MemoryManager,
        state: UserState,
        model: str,
        *,
        print: PrintFn = print,
    ) -> None:
        self._client = client
        self._memory = memory
        self._state = state
        self._model = model
        self._print = print

    def run_board(self, dilemma: str) -> None:
        d = dilemma.strip()
        if not d:
            self._print(f"{Fore.RED}Usage: /board [dilemma]{_RST}", file=sys.stderr)
            return

        self._print(f"\n{_HDR}══ Cognitive board · sandbox ══{_RST}")
        self._print(f"{_HDR}The bind:{_RST} {d}\n")

        # Sequential retrieval so the vector store is not read concurrently.
        contexts: list[tuple[_Persona, str]] = []
        for persona in _PERSONAS:
            hits = self._memory.search_relevant_events(
                f"{d} {persona.memory_bias}",
                limit=5,
            )
            contexts.append((persona, _format_memory_hits(hits)))

        def _one_completion(idx: int, persona: _Persona, mem_block: str) -> tuple[int, str, str]:
            user = (
                f"The bind:\n{d}\n\n{mem_block}\n\n"
                "From your seat, give: stance → key arguments (cite memory numbers if useful) → "
                "a pointed rebuttal of the other two seats (Radical breaker / Rational analyst / Deep reflector). "
                "Stay under 900 words. No JSON. English only."
            )
            messages = [
                {"role": "system", "content": persona.system},
                {"role": "user", "content": user},
            ]
            text = _chat_once(
                self._client,
                self._model,
                messages,
                temperature=persona.temperature,
            )
            return idx, persona.label, text

        ordered: list[tuple[str, str] | None] = [None] * len(_PERSONAS)
        with ThreadPoolExecutor(max_workers=len(_PERSONAS)) as pool:
            futures = [
                pool.submit(_one_completion, i, contexts[i][0], contexts[i][1])
                for i in range(len(contexts))
            ]
            for fut in as_completed(futures):
                idx, label, text = fut.result()
                ordered[idx] = (label, text)

        for i, item in enumerate(ordered, start=1):
            if item is None:
                continue
            label, text = item
            self._print(f"{_HDR}── Node {i} · {label} ──{_RST}")
            self._print(f"{_BODY}{text}{_RST}\n")

        # One-pass synthesis of the clash
        bundle = "\n\n".join(
            f"[{label}]\n{text}"
            for slot in ordered
            if slot is not None
            for label, text in [slot]
        )
        syn = _chat_once(
            self._client,
            self._model,
            [
                {
                    "role": "system",
                    "content": (
                        "You are the board clerk: map disagreement only. Do not invent facts. "
                        "Two English paragraphs: (1) the three axes of conflict; "
                        "(2) each seat's strongest strike on the others. ≤ 500 words."
                    ),
                },
                {"role": "user", "content": bundle},
            ],
            temperature=0.42,
            max_tokens=700,
        )
        self._print(f"{_HDR}── Node IV · clash ──{_RST}")
        self._print(f"{_BODY}{syn}{_RST}\n")

    def run_simulate(self, choice: str) -> None:
        c = choice.strip()
        if not c:
            self._print(
                f"{Fore.RED}Usage: /simulate [choice or path]{_RST}",
                file=sys.stderr,
            )
            return

        self._print(f"\n{_HDR}══ Stepped simulation · 3 months ══{_RST}")
        self._print(f"{_HDR}Path:{_RST} {c}\n")

        for month in range(1, 4):
            self._print(f"{_HDR}── Month {month}/3 ──{_RST}")
            friction_line, roll_note = _roll_friction(self._state)
            if friction_line:
                self._print(f"{_WARN}[Outside friction] {friction_line}{_RST}")
            else:
                self._print(f"{_HDR}[Outside friction] none ({roll_note}){_RST}")

            st = self._state
            user = (
                f"[Stepped simulation · month {month}/3] Grain: one month.\n"
                f"Chosen path: {c}\n"
                f"Physical now: capital={st.capital:.2f}, energy={st.energy:.2f}, "
                f"entropy_rate={st.entropy_rate:.2f}\n"
                f"This month's outside friction: {friction_line or 'none (or did not land)'}\n\n"
                "In concise English, walk the causal chain for this month on this path "
                "(mood and resource constraints included). Do not restate the JSON protocol.\n"
                "End with the same Markdown JSON block the app expects, three fields only: "
                "capital_delta, energy_delta, entropy_rate_delta — the **marginal** effect of "
                "this path this month (if friction already landed, do not double-count it)."
                f"\n\n{deduction_instruction_block(st)}"
            )
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are Digital Twin's monthly sandbox: cold, causal, no pep talk. "
                        "Honor the physical JSON protocol at the end of the user message. English only."
                    ),
                },
                {"role": "user", "content": user},
            ]
            raw = _chat_once(self._client, self._model, messages, temperature=0.55)
            display, outcome = evaluate_deduction_reply(self._state, raw)

            if outcome == "intercepted":
                self._print(f"{Fore.RED}{PHYSICAL_ALERT}{_RST}\n")
                break

            self._print(f"{_BODY}{display}{_RST}\n")
            if outcome == "no_json":
                self._print(
                    f"{_WARN}[System] Month {month}: no valid JSON; state only includes friction if any.{_RST}",
                    file=sys.stderr,
                )

        self._print(f"{_HDR}── Physical remainder ──{_RST}")
        s = self._state
        self._print(
            f"{_HDR}capital={s.capital:.2f}  energy={s.energy:.2f}  "
            f"entropy_rate={s.entropy_rate:.2f}{_RST}\n"
        )
