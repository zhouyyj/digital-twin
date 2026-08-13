# Mirror Image

Geek-flavored CLI digital twin and cognitive sandbox: a restrained mirror persona, long-term episodic memory, a hard physical state machine, multi-agent board debates, stepped monthly sims — and a keyboard twin that senses typing *tempo* without keylogging.

## Phases

| Phase | What |
|-------|------|
| 0 | Terminal loop, Colorama, streamed OpenAI replies |
| 1 | Event-sourced memory (`MemoryManager` + ChromaDB) |
| 2 | Physical state machine (`state.json`, deduction intercepts) |
| 3 | Cognitive sandbox (`/board`, `/simulate`) |
| 4 | Keyboard twin (`/twin` via pynput — rhythm only) |

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env → set OPENAI_API_KEY
python main.py
```

On macOS, `/twin start` needs **Accessibility** permission for your terminal (System Settings → Privacy & Security → Accessibility).

## Commands

- Chat normally — mirror persona streams back
- `/state` — capital / energy / entropy_rate (+ twin status)
- `/board [困境]` — three-director debate with memory citations
- `/simulate [选择]` — 3-month stepped path with entropy friction
- `/twin start|stop|pulse|status` — cognitive tempo sensor (no key contents stored)

## Privacy

Keyboard twin records inter-key intervals and burst structure only. It never stores which keys were pressed. Session summaries are written as `User_Thought` events for later retrieval.
