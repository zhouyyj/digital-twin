"""Digital Twin web server — FastAPI front for chat, watering, and sandbox."""

from __future__ import annotations

import json
import re
import shutil
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from pydantic import BaseModel, Field

from core.config import (
    get_openai_api_key,
    get_openai_base_url,
    get_openai_model,
    get_project_root,
    load_env,
)
from core.feeder import PersonalFeeder
from core.life_path import LifePathEngine
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
    "你是我的数字分身，说话极其克制、一针见血，习惯用提问来剖析我的思维逻辑。"
    "你可以调用用户主动浇灌进记忆的日记、文档与图像描述；不要假装看见未被提供的私料。"
)

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._\-\u4e00-\u9fff]+")
_MAX_UPLOAD_BYTES = 25 * 1024 * 1024


class AppRuntime:
    def __init__(self) -> None:
        load_env()
        try:
            api_key = get_openai_api_key()
        except RuntimeError as exc:
            raise RuntimeError(str(exc)) from exc
        self.model = get_openai_model()
        self.client = OpenAI(api_key=api_key, base_url=get_openai_base_url())
        self.memory = MemoryManager(self.client)
        self.state = UserState.load()
        self.feeder = PersonalFeeder(
            self.client, self.memory, model=self.model, print=lambda *_a, **_k: None
        )
        self.sandbox = CognitiveSandbox(
            self.client, self.memory, self.state, self.model, print=self._capture_print
        )
        self.life_path = LifePathEngine(
            self.client, self.memory, self.state, model=self.model
        )
        # Seed graph immediately; LLM refresh happens on first /api/life-path if still seed
        self.life_path.load_or_seed()
        self.messages: list[dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ]
        self._capture: list[str] = []
        self.upload_dir = get_project_root() / ".uploads"
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def after_water(self, reason: str) -> dict[str, Any]:
        """Archive current future into history and grow a new 3-month tree."""
        try:
            return self.life_path.regenerate(reason=reason, archive=True)
        except Exception as exc:
            data = self.life_path.load_or_seed()
            data["regen_error"] = str(exc)
            return data

    def _capture_print(self, *args: Any, **kwargs: Any) -> None:
        # Strip ANSI-ish callers still pass colorama codes; store plain via str join.
        text = " ".join(str(a) for a in args)
        # Drop common colorama sequences if present.
        text = re.sub(r"\x1b\[[0-9;]*m", "", text)
        self._capture.append(text)

    def take_capture(self) -> str:
        out = "\n".join(self._capture).strip()
        self._capture.clear()
        return out


runtime: AppRuntime | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global runtime
    try:
        runtime = AppRuntime()
    except RuntimeError as exc:
        runtime = None
        _app.state.boot_error = str(exc)
    else:
        _app.state.boot_error = None
    yield


app = FastAPI(title="Digital Twin", lifespan=lifespan)
WEB_DIR = get_project_root() / "web"
app.mount("/assets", StaticFiles(directory=WEB_DIR), name="assets")


def _rt() -> AppRuntime:
    if runtime is None:
        err = getattr(app.state, "boot_error", None) or "Server not ready."
        raise HTTPException(status_code=503, detail=err)
    return runtime


def _memory_augmented(user_line: str, memory: MemoryManager) -> str:
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


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=8000)


class NoteIn(BaseModel):
    note: str = Field(min_length=1, max_length=20000)


class BoardIn(BaseModel):
    dilemma: str = Field(min_length=1, max_length=4000)


class SimulateIn(BaseModel):
    choice: str = Field(min_length=1, max_length=4000)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, Any]:
    if runtime is None:
        return {"ok": False, "error": getattr(app.state, "boot_error", "not ready")}
    return {"ok": True, "model": runtime.model}


@app.get("/api/state")
def get_state() -> dict[str, Any]:
    rt = _rt()
    return {
        **asdict(rt.state),
        "memory_events": rt.memory.count_events(),
    }


@app.post("/api/chat")
async def chat(body: ChatIn) -> StreamingResponse:
    rt = _rt()
    user_line = body.message.strip()
    if not user_line:
        raise HTTPException(status_code=400, detail="Empty message")

    deduction_mode = is_deduction_request(user_line)
    user_for_model = _memory_augmented(user_line, rt.memory)
    if deduction_mode:
        user_for_model = user_for_model + "\n\n" + deduction_instruction_block(rt.state)
    turn_messages = [*rt.messages, {"role": "user", "content": user_for_model}]

    async def gen() -> AsyncIterator[str]:
        try:
            if deduction_mode:
                yield _sse({"type": "status", "text": "推演中…"})
                stream = rt.client.chat.completions.create(
                    model=rt.model,
                    messages=turn_messages,
                    stream=True,
                )
                buf: list[str] = []
                for event in stream:
                    if not event.choices:
                        continue
                    delta = event.choices[0].delta
                    if delta and delta.content:
                        buf.append(delta.content)
                full = "".join(buf)
                display, outcome = evaluate_deduction_reply(rt.state, full)
                if outcome == "intercepted":
                    yield _sse({"type": "alert", "text": PHYSICAL_ALERT_CN})
                    yield _sse({"type": "done", "state": asdict(rt.state)})
                    return
                if outcome == "no_json":
                    yield _sse(
                        {
                            "type": "warn",
                            "text": "未解析到有效的状态消耗 JSON，物理数值未变更。",
                        }
                    )
                reply = display
                # Stream display in small chunks for UI parity
                step = 12
                for i in range(0, len(reply), step):
                    yield _sse({"type": "token", "text": reply[i : i + step]})
            else:
                stream = rt.client.chat.completions.create(
                    model=rt.model,
                    messages=turn_messages,
                    stream=True,
                )
                buf = []
                for event in stream:
                    if not event.choices:
                        continue
                    delta = event.choices[0].delta
                    if delta and delta.content:
                        buf.append(delta.content)
                        yield _sse({"type": "token", "text": delta.content})
                reply = "".join(buf)

            rt.messages.append({"role": "user", "content": user_line})
            rt.messages.append({"role": "assistant", "content": reply})
            try:
                rt.memory.add_event(user_line, "User_Thought")
                rt.memory.add_event(reply, "AI_Intervention")
            except Exception as exc:
                yield _sse({"type": "warn", "text": f"记忆写入失败：{exc}"})

            yield _sse(
                {
                    "type": "done",
                    "state": {
                        **asdict(rt.state),
                        "memory_events": rt.memory.count_events(),
                    },
                }
            )
        except Exception as exc:
            yield _sse({"type": "error", "text": str(exc)})

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/api/water/note")
def water_note(body: NoteIn) -> dict[str, Any]:
    rt = _rt()
    results = rt.feeder.water(f"note: {body.note.strip()}")
    life = rt.after_water("water:note")
    return {
        "ok": True,
        "results": [_result_dict(r) for r in results],
        "memory_events": rt.memory.count_events(),
        "life_path": life,
    }


@app.post("/api/water/upload")
async def water_upload(files: list[UploadFile] = File(...)) -> dict[str, Any]:
    rt = _rt()
    if not files:
        raise HTTPException(status_code=400, detail="No files")

    batch_dir = rt.upload_dir / uuid.uuid4().hex
    batch_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    try:
        for upload in files:
            raw_name = upload.filename or "upload.bin"
            safe = _SAFE_NAME.sub("_", Path(raw_name).name).strip("._") or "upload.bin"
            dest = batch_dir / safe
            # avoid overwrite
            if dest.exists():
                dest = batch_dir / f"{dest.stem}_{uuid.uuid4().hex[:6]}{dest.suffix}"
            size = 0
            with dest.open("wb") as out:
                while True:
                    chunk = await upload.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > _MAX_UPLOAD_BYTES:
                        raise HTTPException(
                            status_code=413,
                            detail=f"{safe} exceeds 25MB limit",
                        )
                    out.write(chunk)
            saved.append(dest)

        all_results = []
        for path in saved:
            all_results.extend(rt.feeder.water(str(path)))

        life = rt.after_water("water:upload")
        return {
            "ok": True,
            "results": [_result_dict(r) for r in all_results],
            "memory_events": rt.memory.count_events(),
            "life_path": life,
        }
    except HTTPException:
        shutil.rmtree(batch_dir, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(batch_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/life-path")
def get_life_path(refresh: bool = False) -> dict[str, Any]:
    rt = _rt()
    if refresh:
        return rt.life_path.regenerate(reason="manual", archive=True)
    data = rt.life_path.load_or_seed()
    if data.get("trigger") == "seed":
        try:
            return rt.life_path.regenerate(reason="boot", archive=False)
        except Exception:
            return data
    return data


@app.post("/api/life-path/regenerate")
def regen_life_path() -> dict[str, Any]:
    rt = _rt()
    return rt.life_path.regenerate(reason="manual", archive=True)


class LifePathEdits(BaseModel):
    positions: dict[str, dict[str, float]] = Field(default_factory=dict)
    edits: dict[str, dict[str, str]] = Field(default_factory=dict)


@app.patch("/api/life-path")
def patch_life_path(body: LifePathEdits) -> dict[str, Any]:
    rt = _rt()
    return rt.life_path.apply_edits(positions=body.positions, edits=body.edits)


@app.post("/api/board")
def board(body: BoardIn) -> dict[str, Any]:
    rt = _rt()
    rt.take_capture()
    try:
        rt.sandbox.run_board(body.dilemma.strip())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"ok": True, "output": rt.take_capture(), "state": asdict(rt.state)}


@app.post("/api/simulate")
def simulate(body: SimulateIn) -> dict[str, Any]:
    rt = _rt()
    rt.take_capture()
    try:
        rt.sandbox.run_simulate(body.choice.strip())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {
        "ok": True,
        "output": rt.take_capture(),
        "state": {
            **asdict(rt.state),
            "memory_events": rt.memory.count_events(),
        },
    }


def _result_dict(r: Any) -> dict[str, Any]:
    return {
        "path": r.path,
        "kind": r.kind,
        "chunks": r.chunks,
        "event_ids": list(r.event_ids),
    }


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
