# Mirror Image

Geek-flavored digital twin and cognitive sandbox: a restrained mirror persona, long-term episodic memory you *water* with personal artifacts, a hard physical state machine, multi-agent board debates, and stepped monthly sims.

Use it from the **terminal** or the **local website** (drag-and-drop watering + streamed chat).

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env → set OPENAI_API_KEY
```

### Website (recommended)

```bash
uvicorn server:app --reload --port 8787
```

Open [http://127.0.0.1:8787](http://127.0.0.1:8787)

- Drag diaries / PDFs / images onto **浇灌**
- Chat in the **会话** tab
- Open **人生路径** for a Wait-But-Why-style past / TODAY / 3-month future tree (regenerates after watering; old trees stay in history)
- `/board` and `/simulate` from the side rail

### Terminal CLI

```bash
python main.py
```

## Phases

| Phase | What |
|-------|------|
| 0 | Terminal loop, Colorama, streamed OpenAI replies |
| 1 | Event-sourced memory (`MemoryManager` + ChromaDB) |
| 2 | Physical state machine (`state.json`, deduction intercepts) |
| 3 | Cognitive sandbox (`/board`, `/simulate`) |
| 4 | Personal watering (`/water` or web drag-drop) |
| 5 | Local web UI (`server.py` + `web/`) |

## CLI commands

- Chat normally — mirror persona streams back
- `/state` — capital / energy / entropy_rate
- `/memory` — how many events are in the local store
- `/board [困境]` — three-director debate with memory citations
- `/simulate [选择]` — 3-month stepped path with entropy friction
- `/water <path>` — feed a file or directory
- `/water note: …` — feed an inline diary line
- `/feed …` — alias of `/water`

## Watering

Nothing is scraped in the background. You explicitly pour material in via CLI or by dropping files on the site.

- Text / markdown / diary → chunked embeddings
- PDF / Word → text extracted, then chunked
- Images → vision caption stored as `Image_Artifact`
