# Mirror Image

Geek-flavored CLI digital twin and cognitive sandbox: a restrained mirror persona, long-term episodic memory you *water* with personal artifacts, a hard physical state machine, multi-agent board debates, and stepped monthly sims.

## Phases

| Phase | What |
|-------|------|
| 0 | Terminal loop, Colorama, streamed OpenAI replies |
| 1 | Event-sourced memory (`MemoryManager` + ChromaDB) |
| 2 | Physical state machine (`state.json`, deduction intercepts) |
| 3 | Cognitive sandbox (`/board`, `/simulate`) |
| 4 | Personal watering (`/water` — diary, docs, images → memory) |

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env → set OPENAI_API_KEY
python main.py
```

## Commands

- Chat normally — mirror persona streams back
- `/state` — capital / energy / entropy_rate
- `/memory` — how many events are in the local store
- `/board [困境]` — three-director debate with memory citations
- `/simulate [选择]` — 3-month stepped path with entropy friction
- `/water <path>` — feed a file or directory (txt/md/pdf/docx/png/jpg/…)
- `/water note: …` — feed an inline diary line
- `/feed …` — alias of `/water`

## Watering

Nothing is scraped in the background. You explicitly pour material in:

```text
/water ~/Diary/2024-spring.md
/water ./scrapbook/photos
/water note: 搬家第三天，纸箱还没拆，但睡眠终于回来了。
```

- Text / markdown / diary → chunked and embedded as `Diary_Entry` or `Document_Artifact`
- PDF / Word → text extracted, then chunked
- Images → vision model writes a personal-memory caption, stored as `Image_Artifact`

Later chat, `/board`, and deductions retrieve these the same way as conversation memory.
