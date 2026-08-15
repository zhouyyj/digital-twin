# Mirror

**A personal world simulator grounded in evidence, uncertainty, and actual choices.**

Mirror is not a generic advice bot and it does not ask you to rate your life with precise
energy or money scores. You add observations, diaries, documents, and images. Mirror turns
that evidence into a revisable Twin Model, then uses it to simulate possible worlds that are
specific to your patterns and constraints.

## The product loop

1. **Add evidence** — a note, diary, document, or photo.
2. **Revise the Twin Model** — values, repeated patterns, constraints, assets, tensions, and
   unknowns are stored with evidence and confidence.
3. **Test a hypothesis** — ask the mirror, compare a conflict, or run three counterfactual
   worlds over three months.
4. **Inspect possible worlds** — branches show qualitative pressure, plausibility, supporting
   evidence, and uncertainty rather than invented resource precision.
5. **Commit deliberately** — a selected path is recorded as a choice, not as an event that has
   already happened.
6. **Return with reality** — later observations revise the model and expose where the simulation
   was wrong.

## Epistemic model

Mirror keeps three kinds of information visibly separate:

- **Observed** — material the user actually provided.
- **Inferred** — revisable claims supported by one or more observations.
- **Unknown** — variables that could materially change a simulation.

The previous capital / energy / entropy meters remain only as legacy compatibility code for old
local state files. They are not part of the current product interface or the new simulation
protocol. Weak evidence is expressed as uncertainty, not converted into a number.

## What is implemented

- Local ChromaDB memory with OpenAI embeddings
- Evidence ingestion for text, Markdown, PDF, Word, and images
- Durable `twin_profile.json` model with evidence references and confidence
- Streamed, memory-augmented mirror conversation
- Three-position cognitive board
- Base / Support / Friction counterfactual simulation
- Branching 2–6 month world map
- Qualitative pressure and plausibility on each generated branch
- Explicit path commitment
- Reality-check observations that revise the model and recalculate worlds
- Separate archive of previous predictions

## Run locally

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# add OPENAI_API_KEY to .env
uvicorn server:app --reload --port 8787
```

Open [http://127.0.0.1:8787](http://127.0.0.1:8787).

The app and persistent data run locally, but content used for embeddings, vision, and model
responses is sent to the API configured by `OPENAI_BASE_URL`. “Local” does not mean offline.

## Terminal

```bash
python main.py
```

- `/model` — current Twin Model summary, confidence, and unknown count
- `/memory` — number of stored observations and interventions
- `/board [dilemma]` — compare the conflict from three positions
- `/simulate [hypothesis]` — Base / Support / Friction three-month worlds
- `/water <path>` — add a file or directory as evidence
- `/water note: …` — add an observation

Runtime artifacts are intentionally untracked: `.chroma_db/`, `.uploads/`, `life_path.json`,
`twin_profile.json`, and legacy `state.json`.
