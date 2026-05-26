# LLM Yield Engine

A **local-first, SOP-driven wafer yield analysis agent**. Ask in natural language ("analyze this wafer lot"), and a ReAct agent — running entirely on your own machine via Ollama — loads the engineering SOP, calls MCP tools to read the data and render plots, runs vision-language analysis on each plot, and emits a self-contained archived report.

No cloud calls. No API keys. Wafer data and analyses never leave the host.

---

## How it works

### Component topology

```mermaid
flowchart LR
    U([User]) -->|ask| FE[Frontend]
    FE -->|/agent/stream| BE[Backend]
    BE -->|launch| LOOP

    subgraph LOOP["🔄 ReAct Loop · SOP-driven"]
        direction TB
        R[Reason] --> A[Act] --> O[Observe] --> R
    end

    LOOP <-->|reason / vision| LLM[(🤖 Ollama)]
    LOOP <-->|call tool| MCP[🔧 MCP Tools]
    LOOP -->|done| REPORT[📄 Report]
    REPORT -.->|stream back| FE

    classDef sat fill:#fef,stroke:#c8c
    class LLM,MCP sat
```

### What's actually happening

1. **Frontend** posts the user's message to `/agent/stream`. The backend's `_needs_agent()` router decides: small talk goes straight to Ollama (`qwen3:8b`); an analysis request enters the ReAct agent.
2. **SOP is loaded first.** [`agent/sop/engineering.md`](backend/app/agent/sop/engineering.md) defines the *Fixed Steps* (`get_wafer_info` → binary map → PIN properties → P-charts) and the *Adaptive Investigation* rules. Its body is injected as the system prompt, so every run starts with the same evidence chain.
3. **ReAct loop** (`reason → act → observe`):
   - **Reason** — the planner LLM picks the next tool (or declares it's done).
   - **Act** — the MCP server actually opens the ZIP, runs the analysis, and renders the plot.
   - **Observe** — visual results are passed back through a vision-language pass; the resulting text observation is appended to the scratchpad for the next round.
4. **Safety caps**: `REACT_MAX_ITERS = 12`, `REACT_MAX_ERRORS = 3`. If hit, the agent is forced to write a conclusion from what it already has.
5. **Report builder** assembles a self-contained folder under [`reports/`](reports/) per the template in [`report_format_example.md`](report_format_example.md): `report.md` + `images/*.png`. The frontend exposes a one-click `.zip` download.

---

## Repository layout

```
LLM_Yield_Engine/
├── README.md                       this file
├── ARCHITECTURE.md                 deeper component diagrams
├── report_format_example.md        template the report builder follows
├── requirements.txt                Python deps (backend + MCP share one venv)
│
├── backend/                        FastAPI service · :8000
│   └── app/
│       ├── main.py                 routes: /chat/stream, /agent/stream, /report/*
│       ├── mcp_client/             HTTP client for the MCP server
│       └── agent/
│           ├── config.py           models, data path, safety caps, reports dir
│           ├── report.py           assembles report.md + images/
│           ├── vision_analyst.py   VL streaming wrapper for plot analysis
│           ├── react/              ReAct loop (loop · reasoner · tool_runner · observation · policy)
│           └── sop/                engineering.md + loader
│
├── frontend/                       React + Vite UI · :5173
│
├── mcp/                            FastMCP tool server · :8001
│   ├── server.py
│   └── tools/
│       ├── information_read/       get_wafer_info
│       ├── statistic_plot/         P-chart rendering
│       ├── wafer_map/              binary map · PIN property maps
│       └── workflow/               run_wafer_analysis (composite)
│
├── raw_data_example/
│   └── wafer_data/sample_1.zip     CSV inside: BIN, X, Y, WAFER_ID, PIN_1..PIN_N
│
└── reports/                        generated per run (gitignored)
```

---

## Prerequisites

- **Python 3.11+**
- **Node.js 18+** (for the frontend)
- **[Ollama](https://ollama.com/)** running locally with these models pulled:
  ```bash
  ollama pull qwen3.5:4b   # planner + vision (used by the agent)
  ollama pull qwen3:8b     # plain chat fallback
  ```

---

## Install

```bash
# 1. Python deps (use a venv)
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # macOS / Linux
pip install -r requirements.txt

# 2. Frontend deps
cd frontend
npm install
cd ..
```

---

## Run (4 terminals)

| # | Service | Command | Port |
|---|---|---|---|
| 1 | Ollama | `ollama serve` | 11434 |
| 2 | MCP server | `python mcp/server.py` | 8001 |
| 3 | Backend | `uvicorn backend.app.main:app --reload --port 8000` | 8000 |
| 4 | Frontend | `cd frontend && npm run dev` | 5173 |

Open <http://localhost:5173> and try:

> *"Hi, please analyze the sample wafer data."*

You should see the Thinking panel stream the SOP steps, the chat bubble fill with images and analyses, and a Report tab appear with a download button.

---

## Configuration

Knobs live in [`backend/app/agent/config.py`](backend/app/agent/config.py):

| Variable | Default | What it does |
|---|---|---|
| `PLANNER_MODEL` / `VISION_MODEL` | `qwen3.5:4b` | Ollama model tag for the agent |
| `DEFAULT_FILE` | `raw_data_example/wafer_data/sample_1.zip` | Data file when the user doesn't specify one. Overridable via `WAFER_DATA_FILE` env var. |
| `REACT_MAX_ITERS` | `12` | Hard cap on reasoning rounds |
| `REACT_MAX_ERRORS` | `3` | Abort after this many failed tool calls |
| `REPORTS_DIR` | `reports/` at repo root | Where archived runs are written |

Point at a different data file:
```bash
# Windows PowerShell
$env:WAFER_DATA_FILE = "C:\path\to\your\wafer.zip"
uvicorn backend.app.main:app --reload --port 8000
```

---

## Adding a new MCP tool

1. Drop the implementation under `mcp/tools/<category>/your_tool.py` and expose a function.
2. Register it in [`mcp/server.py`](mcp/server.py) with `@mcp.tool()`.
3. Add the tool's JSON schema to `REACT_TOOLS` in [`backend/app/agent/react/tool_runner.py`](backend/app/agent/react/tool_runner.py) so the planner knows about it.
4. (Optional) Reference it in the SOP at [`backend/app/agent/sop/engineering.md`](backend/app/agent/sop/engineering.md) if it belongs in the Fixed Steps.

---

## License

[MIT](LICENSE) © 2026 Cheng Wei Tseng.
