# WebUI System Architecture

---

## 1. System Overview

```mermaid
graph TB
    subgraph CLIENT["🖥️  Browser"]
        UI["WebUI\nlocalhost:5173"]
    end

    subgraph BE["⚙️  Backend  —  FastAPI  :8000"]
        B1["/chat/stream\nDirect chat proxy"]
        B2["/agent/stream\nPlan-and-Execute agent"]
    end

    subgraph MCP["🔧  MCP Tool Server  —  FastMCP  :8001"]
        M1["run_wafer_analysis"]
        M2["plot_wafer_bin"]
        M3["plot_wafer_property"]
        M4["get_wafer_info"]
    end

    subgraph OLLAMA["🤖  Ollama  :11434"]
        O1["qwen3:8b\nPlanner / Chat"]
        O2["qwen3-vl:latest\nVision Analysis"]
    end

    subgraph DATA["💾  Data"]
        D1["sample_1.zip\nBIN, X, Y, WAFER_ID, PIN_1~5"]
    end

    UI -->|"NDJSON stream"| B1
    UI -->|"NDJSON stream"| B2
    B1 -->|"httpx stream"| O1
    B2 -->|"Plan"| O1
    B2 -->|"MCP Streamable HTTP"| MCP
    B2 -->|"Vision"| O2
    MCP --> D1

    style CLIENT fill:#dbeafe,stroke:#3b82f6
    style BE     fill:#dcfce7,stroke:#16a34a
    style MCP    fill:#fef9c3,stroke:#ca8a04
    style OLLAMA fill:#f3e8ff,stroke:#9333ea
    style DATA   fill:#fee2e2,stroke:#dc2626
```

---

## 2. Frontend Component Tree

```mermaid
graph TD
    APP["App.tsx\nLayout host + Module Registry"]

    APP --> CHAT["ChatColumn"]
    APP --> RIGHT["Right Panel Slot\n(shown only when streaming)"]

    CHAT --> ML["MessageList"]
    CHAT --> CI["ChatInput\n Send / Stop"]

    ML --> MB["MessageBubble"]
    MB --> MD1["MarkdownMessage\n① pre-image text"]
    MB --> IG["ImageGrid"]
    MB --> MD2["MarkdownMessage\n③ post-image text\n(PIN batch analysis)"]

    IG --> IC1["ImageCell — Binary Map\n  label\n  image (max 220px)\n  ② VL analysis text"]
    IG --> IC2["ImageCell — PIN_1\n  label / image / analysis"]
    IG --> IC3["ImageCell — PIN_2 …"]

    RIGHT --> TP["ThinkingPanel"]
    TP --> TL["ThinkingTimeline"]
    TL --> TN1["ThinkingNode ✅ done"]
    TL --> TN2["ThinkingNode 🔵 active\n(pulsing dot + cursor)"]

    style APP  fill:#dbeafe,stroke:#3b82f6
    style CHAT fill:#dbeafe,stroke:#3b82f6
    style RIGHT fill:#dbeafe,stroke:#3b82f6
    style TP   fill:#ede9fe,stroke:#7c3aed
    style IG   fill:#d1fae5,stroke:#059669
```

---

## 3. Agent Pipeline — Request Flow

```mermaid
sequenceDiagram
    actor User
    participant UI   as Frontend
    participant BE   as Backend
    participant LLM  as qwen3:8b
    participant MCP  as MCP Server
    participant VL   as qwen3-vl

    User->>UI: send message
    UI->>BE: POST /agent/stream

    Note over BE: keyword router<br/>decides agent mode

    BE->>LLM: stream_plan()<br/>generate Step list
    LLM-->>BE: Step 1 — run_wafer_analysis
    BE-->>UI: {type:"thinking"} × N<br/>(plan steps → ThinkingPanel)

    BE->>MCP: call_tool(run_wafer_analysis)
    BE-->>UI: {type:"thinking"} Calling tool…

    MCP-->>BE: [text, image×6]<br/>(summary + binary + 5 PIN maps)

    loop For each item
        alt text item
            BE-->>UI: {type:"delta"} summary text
        else binary map image
            BE-->>UI: {type:"thinking"} Rendering image 1/6
            BE-->>UI: {type:"image"} binary map
            BE->>VL: stream_image_analysis()
            BE-->>UI: {type:"thinking"} VL analysis: Binary Map
            VL-->>BE: analysis chunks
            BE-->>UI: {type:"analysis"} → inside image cell
        else PIN map image
            BE-->>UI: {type:"thinking"} Rendering image N/6
            BE-->>UI: {type:"image"} PIN_N map
            BE-->>UI: {type:"thinking"} Queuing for batch…
            Note over BE: collect all 5 PIN images
        end
    end

    BE->>VL: stream_pin_batch_analysis()<br/>(all 5 PINs at once)
    BE-->>UI: {type:"thinking"} Batch VL analysis…
    VL-->>BE: batch analysis chunks
    BE-->>UI: {type:"postdelta"} PIN Property Analysis
    BE-->>UI: {type:"done"}
```

---

## 4. NDJSON Event Types

```mermaid
graph LR
    subgraph EVENTS["Event Types  (Backend → Frontend)"]
        E1["delta\n→ m.content\n above images"]
        E2["thinking\n→ m.thinkingText\n ThinkingPanel"]
        E3["image\n→ m.images[]\n ImageGrid"]
        E4["analysis\n→ m.images[last].analysis\n below each image"]
        E5["postdelta\n→ m.postContent\n below ImageGrid"]
        E6["done\n→ thinkingDone = true"]
    end

    subgraph BUBBLE["MessageBubble render order"]
        direction TB
        R1["① content  (delta)"]
        R2["② ImageGrid  (image + analysis)"]
        R3["③ postContent  (postdelta)"]
        R1 --> R2 --> R3
    end

    style E1 fill:#dbeafe,stroke:#3b82f6
    style E2 fill:#ede9fe,stroke:#7c3aed
    style E3 fill:#d1fae5,stroke:#059669
    style E4 fill:#d1fae5,stroke:#059669
    style E5 fill:#fef9c3,stroke:#ca8a04
    style E6 fill:#f1f5f9,stroke:#94a3b8
```

---

## 5. Vision Strategy Pattern

```mermaid
graph TD
    CFG["agent/config.py\nVISION_STRATEGY_CLASS = BatchPinStrategy"]
    CFG --> BP

    subgraph STRATEGIES["agent/strategies/"]
        BASE["VisionStrategy (base)\non_image(b64, label, summary)\non_step_complete(images, summary)"]
        NONE["NoAnalysisStrategy\n— skip all VL"]
        IL["InterleavedStrategy\n— every image → VL immediately"]
        BP["BatchPinStrategy  ✅ active\n— binary → VL now\n— PIN maps → collect → batch"]
    end

    BASE --> NONE
    BASE --> IL
    BASE --> BP

    BP -->|"binary image"| VA1["stream_image_analysis()\nsingle image VL call"]
    BP -->|"after all PINs"| VA2["stream_pin_batch_analysis()\nall PIN images in one VL call"]

    style CFG  fill:#ffedd5,stroke:#ea580c
    style BP   fill:#dcfce7,stroke:#16a34a,stroke-width:2px
    style BASE fill:#f1f5f9,stroke:#94a3b8
```

---

## 6. MCP Tool Server

```mermaid
graph TD
    subgraph SERVER["MCP Server  :8001  (FastMCP)"]
        EP["HTTP /mcp\nStreamable HTTP transport"]

        subgraph WF["Workflow"]
            T1["run_wafer_analysis(file_path)\ninfo + binary map + all PIN maps\nin a single call"]
        end

        subgraph PRIM["Primitives"]
            T2["get_wafer_info(file_path)\ntext summary only"]
            T3["plot_wafer_bin(file_path)\nbinary pass/fail map → PNG"]
            T4["plot_wafer_property(file_path, pin_column)\nPIN heatmap → PNG\n(IQR auto-scale)"]
        end

        EP --> T1
        EP --> T2
        EP --> T3
        EP --> T4
    end

    T1 --> ZIP
    T2 --> ZIP
    T3 --> ZIP
    T4 --> ZIP

    ZIP["sample_1.zip\nCSV columns:\nBIN · X · Y · WAFER_ID · PIN_1~PIN_5"]

    style SERVER fill:#fef9c3,stroke:#ca8a04
    style ZIP    fill:#fee2e2,stroke:#dc2626
```
