"""Phase 3 — cognitive board + stepped month simulation."""

from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable

from colorama import Fore, Style
from openai import OpenAI

from core.memory_manager import MemoryManager
from core.state_machine import UserState
from core.twin_model import TwinModel

PrintFn = Callable[..., None]

_HDR = Fore.GREEN + Style.DIM
_BODY = Fore.CYAN
_RST = Style.RESET_ALL


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


class CognitiveSandbox:
    """Board of minds (parallel views + rebuttal) and stepped monthly simulation."""

    def __init__(
        self,
        client: OpenAI,
        memory: MemoryManager,
        state: UserState,
        model: str,
        twin_model: TwinModel | None = None,
        *,
        print: PrintFn = print,
    ) -> None:
        self._client = client
        self._memory = memory
        self._state = state
        self._model = model
        self._twin_model = twin_model
        self._print = print

    def run_board(self, dilemma: str) -> None:
        d = dilemma.strip()
        if not d:
            self._print(f"{Fore.RED}Usage: /board [dilemma]{_RST}", file=sys.stderr)
            return

        self._print(f"\n{_HDR}══ Cognitive board · sandbox ══{_RST}")
        self._print(f"{_HDR}The bind:{_RST} {d}\n")
        twin_context = (
            self._twin_model.compact_context()
            if self._twin_model is not None
            else "(no durable twin model)"
        )

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
                f"Durable twin model:\n{twin_context}\n\n"
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

        self._print(f"\n{_HDR}══ Counterfactual simulation · 3 months ══{_RST}")
        self._print(f"{_HDR}Path:{_RST} {c}\n")
        twin_context = (
            self._twin_model.compact_context()
            if self._twin_model is not None
            else "(no durable twin model)"
        )

        hits = self._memory.search_relevant_events(
            f"{c} past behavior constraint obligation money energy relationship", limit=8
        )
        evidence = _format_memory_hits(hits)
        user = (
            f"Hypothesis to simulate: {c}\n\n"
            f"Revisable twin model:\n{twin_context}\n\n"
            f"Relevant evidence:\n{evidence}\n\n"
            "Simulate three months without inventing exact resource meters. Produce three "
            "counterfactual worlds: BASE (current patterns continue), SUPPORT (one external "
            "condition becomes easier), and FRICTION (one plausible external condition worsens). "
            "For each world, show month 1 → month 2 → month 3 as a causal chain. Distinguish "
            "OBSERVED evidence, INFERRED dynamics, and UNKNOWN variables. Name the first constraint "
            "that becomes binding and one observation that would falsify the simulation. "
            "Do not recommend a world and do not use numerical energy/capital scores."
        )
        output = _chat_once(
            self._client,
            self._model,
            [
                {
                    "role": "system",
                    "content": (
                        "You are a counterfactual world simulator. Be causal, person-specific, "
                        "and explicit about uncertainty. Never turn weak evidence into precision."
                    ),
                },
                {"role": "user", "content": user},
            ],
            temperature=0.45,
            max_tokens=2200,
        )
        self._print(f"{_BODY}{output}{_RST}\n")
