# Digital Twin

<p align="center">
  <img src="docs/preview.png" alt="Digital Twin — chat and life path" width="920" />
</p>

<p align="center">
  <strong>Add files and notes. Then see possible paths.</strong><br />
  A local digital twin with file memory, a physical state machine, and a branching life-path map.
</p>

<p align="center">
  <a href="https://zhouyyj.github.io/digital-twin/">Preview page</a> ·
  <a href="#setup">Run locally</a>
</p>

---

Use it from the **terminal** or the **local website** (drag-and-drop files + streamed chat).

## What you get

| | |
|---|---|
| **Add files** | Drop diaries, PDFs, images — chunked into local Chroma embeddings |
| **Chat** | Streamed twin replies; mention “deduce” / “choose” to count the cost |
| **Life path** | Custom 2–6 months; 3 branches, then 3 from each; nodes you can drag and edit |
| **History** | After you add files, the previous path is saved in History |
| **Sandbox** | Compare options and month-by-month simulation |

The UI is English-only.

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

- Drag diaries / PDFs / images onto **Add files**
- Chat in **Chat**
- Open **Life path** for past / today / future branches (regenerates after you add files; previous paths stay in History)
- Use **− / +** to change horizon months; **Regenerate** to redraw
- Drag nodes; click to edit label and detail

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
| 4 | Add files (`/water` or web drag-drop) |
| 5 | Local web UI (`server.py` + `web/`) |

## CLI commands

- Chat normally — the twin streams back
- `/state` — capital / energy / entropy_rate
- `/memory` — how many events are in the local store
- `/board [dilemma]` — three-director debate with memory citations
- `/simulate [choice]` — stepped path with entropy friction
- `/water <path>` — add a file or directory
- `/water note: …` — add an inline diary line
- `/feed …` — alias of `/water`

## Adding files

Nothing is scraped in the background. You add files via CLI or by dropping them on the site.

- Text / markdown / diary → chunked embeddings
- PDF / Word → text extracted, then chunked
- Images → vision caption stored as `Image_Artifact`

## GitHub preview

- **README** — screenshot above (`docs/preview.png`)
- **GitHub Pages** — enable *Settings → Pages → Build from branch `main`, folder `/docs`* → live at `https://zhouyyj.github.io/digital-twin/`

Replace `docs/preview.png` anytime with a fresh screenshot of your local UI.
