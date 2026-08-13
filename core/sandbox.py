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
    PHYSICAL_ALERT_CN,
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
        label="激进破局者",
        memory_bias="冒险 破局 杠杆 非对称 进攻",
        temperature=0.92,
        system=(
            "你是「激进破局者」董事：押注非对称收益，厌恶拖延；"
            "语言锋利、短句为主，敢于推翻默认假设。"
        ),
    ),
    _Persona(
        label="理性分析师",
        memory_bias="风险 收益 概率 现金流 稳定 数据",
        temperature=0.35,
        system=(
            "你是「理性分析师」董事：用期望值与可验证前提拆解选项；"
            "标出关键不确定性与最坏情形，拒绝空泛励志。"
        ),
    ),
    _Persona(
        label="深度反思者",
        memory_bias="意义 恐惧 身份 后悔 长期 内在动机",
        temperature=0.62,
        system=(
            "你是「深度反思者」董事：追问「谁在害怕什么」与二阶后果；"
            "把困境映射到自我叙事与伦理张力，语气克制但刺骨。"
        ),
    ),
)

_FRICTION_EVENTS: tuple[dict[str, str | float], ...] = (
    {
        "label": "关键设备突发损坏，维修与停工挤占现金",
        "capital_delta": -10.0,
        "energy_delta": -7.0,
        "entropy_rate_delta": 0.02,
    },
    {
        "label": "合作方跳票 / 回款延迟，现金流承压",
        "capital_delta": -14.0,
        "energy_delta": -6.0,
        "entropy_rate_delta": 0.04,
    },
    {
        "label": "舆论黑天鹅，声誉维护消耗带宽",
        "capital_delta": -4.0,
        "energy_delta": -11.0,
        "entropy_rate_delta": 0.05,
    },
    {
        "label": "核心成员临时离职，组织磨合成本上升",
        "capital_delta": -6.0,
        "energy_delta": -12.0,
        "entropy_rate_delta": 0.03,
    },
    {
        "label": "监管或合规抽查，合规支出意外增加",
        "capital_delta": -9.0,
        "energy_delta": -5.0,
        "entropy_rate_delta": 0.02,
    },
)


def _format_memory_hits(hits: list[dict]) -> str:
    if not hits:
        return "（记忆库中暂无相近条目。）"
    lines: list[str] = []
    for i, h in enumerate(hits, start=1):
        ts = h.get("timestamp", "")
        et = h.get("event_type", "")
        body = h.get("text", "")
        lines.append(f"[{i}] {ts} | {et}\n{body}")
    return "与本轮立场相关的记忆片段：\n\n" + "\n\n".join(lines)


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
    """在精力不为负的前提下尽量应用摩擦；必要时缩放增量。"""
    label = str(ev["label"])
    for scale in (1.0, 0.55, 0.3):
        cd = float(ev["capital_delta"]) * scale
        ed = float(ev["energy_delta"]) * scale
        er = float(ev["entropy_rate_delta"]) * scale
        if state.preview_energy_after(ed) < 0:
            continue
        if state.apply_deltas(cd, ed, er):
            suffix = f"（摩擦强度 ×{scale:g}）" if scale < 1.0 else ""
            return True, f"{label}{suffix}"
    return False, label


def _roll_friction(state: UserState) -> tuple[str | None, str]:
    """
    结合 entropy_rate 随机触发外部摩擦。
    返回 (若触发则摩擦说明文案, 人类可读掷骰摘要)。
    """
    p = min(0.9, 0.08 + float(state.entropy_rate) * 1.15)
    roll = random.random()
    summary = f"p={p:.2f}, roll={roll:.3f}, entropy_rate={state.entropy_rate:.2f}"
    if roll >= p:
        return None, summary
    ev = random.choice(_FRICTION_EVENTS)
    ok, desc = _apply_friction_scaled(state, ev)
    if not ok:
        return None, summary + " → 摩擦被物理上限压制，未生效"
    return desc, summary


class CognitiveSandbox:
    """认知董事会（并行观点 + 互驳）与步进式月度物理推演。"""

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
            self._print(f"{Fore.RED}用法：/board [困境描述]{_RST}", file=sys.stderr)
            return

        self._print(f"\n{_HDR}══ 认知董事会 · 沙盒 ══{_RST}")
        self._print(f"{_HDR}核心困境：{_RST}{d}\n")

        # 顺序检索，避免向量库并发读问题；补全并行。
        contexts: list[tuple[_Persona, str]] = []
        for persona in _PERSONAS:
            hits = self._memory.search_relevant_events(
                f"{d} {persona.memory_bias}",
                limit=5,
            )
            contexts.append((persona, _format_memory_hits(hits)))

        def _one_completion(idx: int, persona: _Persona, mem_block: str) -> tuple[int, str, str]:
            user = (
                f"核心困境：\n{d}\n\n{mem_block}\n\n"
                "请站在你的董事席位上给出：立场 → 关键论据（可引用记忆片段编号）→ "
                "对其他两类董事（激进破局者 / 理性分析师 / 深度反思者）常见论点的针对性驳斥。"
                "总字数控制在 900 字以内，不要输出 JSON。"
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
            self._print(f"{_HDR}── 节点 {i} · {label} ──{_RST}")
            self._print(f"{_BODY}{text}{_RST}\n")

        # 合议互驳（基于已得文本，单轮合成）
        bundle = "\n\n".join(
            f"【{label}】\n{text}"
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
                        "你是镜子合议庭书记：只做观点对照与互驳映射，禁止引入新事实或数据。"
                        "用两段中文：① 三方分歧轴；② 各方最有效的相互打击点。总字数 ≤ 500。"
                    ),
                },
                {"role": "user", "content": bundle},
            ],
            temperature=0.42,
            max_tokens=700,
        )
        self._print(f"{_HDR}── 节点 IV · 互驳合取 ──{_RST}")
        self._print(f"{_BODY}{syn}{_RST}\n")

    def run_simulate(self, choice: str) -> None:
        c = choice.strip()
        if not c:
            self._print(
                f"{Fore.RED}用法：/simulate [你的选择或路径描述]{_RST}",
                file=sys.stderr,
            )
            return

        self._print(f"\n{_HDR}══ 步进式推演 · 3 个月 ══{_RST}")
        self._print(f"{_HDR}路径锚定：{_RST}{c}\n")

        for month in range(1, 4):
            self._print(f"{_HDR}── 第 {month}/3 月 ──{_RST}")
            friction_line, roll_note = _roll_friction(self._state)
            if friction_line:
                self._print(f"{_WARN}[外部摩擦] {friction_line}{_RST}")
            else:
                self._print(f"{_HDR}[外部摩擦] 未触发（{roll_note}）{_RST}")

            st = self._state
            user = (
                f"【步进式推演 · 第 {month}/3 月】时间粒度：月。\n"
                f"用户选择路径：{c}\n"
                f"当前物理状态：capital={st.capital:.2f}, energy={st.energy:.2f}, "
                f"entropy_rate={st.entropy_rate:.2f}\n"
                f"本月外部摩擦：{friction_line or '无（或未成功入账）'}\n\n"
                "请用简练中文推演本月在该路径下的关键因果链（含情绪与资源约束），"
                "不要复述系统 JSON 要求的长说明。\n"
                "在全文最后附上与主程序一致的 Markdown JSON 代码块，仅含三字段："
                "capital_delta, energy_delta, entropy_rate_delta；"
                "表示**本月叙事中该路径带来的边际后果**（摩擦若已入账，JSON 只写路径本身的额外冲击，避免与摩擦重复夸大）。"
                f"\n\n{deduction_instruction_block(st)}"
            )
            messages = [
                {
                    "role": "system",
                    "content": (
                        "你是 Digital Twin 的月度沙盘引擎：冷峻、因果清晰，拒绝鸡汤。"
                        "严格遵守用户在文末追加的物理 JSON 协议。"
                    ),
                },
                {"role": "user", "content": user},
            ]
            raw = _chat_once(self._client, self._model, messages, temperature=0.55)
            display, outcome = evaluate_deduction_reply(self._state, raw)

            if outcome == "intercepted":
                self._print(f"{Fore.RED}{PHYSICAL_ALERT_CN}{_RST}\n")
                break

            self._print(f"{_BODY}{display}{_RST}\n")
            if outcome == "no_json":
                self._print(
                    f"{_WARN}[系统] 第 {month} 月未解析到有效 JSON，状态仅含摩擦变更（若有）。{_RST}",
                    file=sys.stderr,
                )

        self._print(f"{_HDR}── 推演后物理残余 ──{_RST}")
        s = self._state
        self._print(
            f"{_HDR}capital={s.capital:.2f}  energy={s.energy:.2f}  "
            f"entropy_rate={s.entropy_rate:.2f}{_RST}\n"
        )
