---
name: Standard Yield Analysis
department: Engineering
version: 1.0
---

# Standard Yield Analysis SOP — Engineering

Standard procedure for analysing a single wafer data file (CSV or ZIP with
columns `BIN, X, Y, WAFER_ID, Wafer_lot_name, PIN_1..PIN_N`).

The agent runs **every Fixed Step below, in order** — this guaranteed
sequence is the evidence chain for root-cause analysis. Only after the fixed
steps are complete does the agent perform adaptive follow-up.

## 1. Fixed Steps

The engine executes exactly these steps, in this order, on every run.
`get_wafer_info` runs first to establish the baseline and discover the PIN
columns; the three plotting steps are the analysis SOP.

```yaml
- tool: get_wafer_info
  goal: Baseline — yield, pass/fail counts, available PIN columns
- tool: plot_binary_map
  goal: Observe the spatial distribution of all failing dies
- tool: plot_pin_properties
  pin_columns: all
  goal: Inspect the measurement uniformity of every PIN
- tool: plot_pin_pchart
  pin_columns: all
  goal: Check the value distribution / normality of every PIN
```

## 2. Execution & Output Rules

- **Interleaved analysis.** Immediately after each image is rendered, analyse
  its features before moving on to the next step. Do not defer analysis to
  the end of the run.
- **Tables in the conclusion.** When the conclusion compares numbers across
  PINs, or maps root causes to evidence, present them as Markdown tables —
  not prose. (Per-image statistics are added to the report automatically.)

## 3. Adaptive Investigation

After the fixed steps, investigate further based on what was observed.
Hints below — extend this list with department domain knowledge:

- Failures forming an edge ring → suspect edge process / temperature gradient.
- A PIN with an abnormally wide IQR spread → focus deeper analysis on that PIN.
- Failures clustered at the centre → suspect chuck / process non-uniformity.

## 4. Conclusion Requirements

Your conclusion becomes the **Conclusion** section of an automatically
assembled report that already contains every image, its statistics and its
per-step analysis. SYNTHESISE the findings — do not repeat the raw data.
The conclusion must:

1. **Describe the problems found** — fail pattern, abnormal PINs, affected
   regions.
2. **Give an actionable direction** — at minimum a concrete next step or
   corrective guidance, not only a description of the symptoms.
3. **Reference the Fixed Steps** as the supporting evidence chain.