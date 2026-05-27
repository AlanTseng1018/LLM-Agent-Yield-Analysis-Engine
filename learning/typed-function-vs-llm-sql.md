# Typed Function vs LLM-Generated SQL

> Which is the right way to do data access in an engineering-grade LLM agent?

---

## The question

When an engineering LLM agent needs to read from a database (or any structured store), there are two design philosophies. They look similar from the outside, but they lead to completely different systems.

| Option | What the LLM does | Where the SQL lives |
|---|---|---|
| **A. Generic SQL executor** | Generates a SQL string | The LLM writes it on the fly |
| **B. Typed function** | Fills typed parameters of a named function | Written by hand in Python, frozen at build time |

The intuition many people start with: "Option A is more flexible — one function, the LLM can ask any question." This intuition is **wrong** for engineering environments. Here is the long version of why.

---

## Option A — Generic SQL executor

```python
def query_from_db(sql: str) -> list[dict]:
    return db.execute(sql).fetchall()
```

Registered as one MCP tool. The LLM, in its reasoning step, generates strings like:

```sql
SELECT lot_id, yield FROM lots
WHERE date >= '2026-05-20' AND yield < 85
ORDER BY yield ASC LIMIT 10
```

…and the framework runs it. Looks elegant. One tool, infinite query power.

## Option B — Typed function

```python
def list_lots(
    week: str | None = None,
    product: str | None = None,
    min_yield: float = 0,
    max_yield: float = 100,
    order_by: str = "yield",   # restricted to {"yield", "date", "lot_id"}
    limit: int = 50,
) -> list[dict]:
    """List wafer lots matching the given filters."""
    # SQL is written here, by hand, once.
    # The LLM never sees it.
    ...
```

Registered as one MCP tool. The LLM produces a structured tool call:

```json
{ "name": "list_lots", "arguments": { "week": "2026-W22", "min_yield": 0, "max_yield": 85, "limit": 10 } }
```

The framework routes it to the Python function. The function builds the SQL from typed parameters using a pattern *you* approved at build time.

---

## The hidden cost — why Option A loses

Option A *looks* like less code, because you only write one wrapper. The cost is hidden in places people don't count on day one. Once you count those, Option B wins on every axis that matters.

| Axis | A — Generic SQL | B — Typed function |
|---|---|---|
| Lines of code written upfront | ~100 (one wrapper) | ~600–900 (5–6 functions) |
| Lines of *prompt* you must write | Big — table schema + few-shot SQL examples baked into the system prompt | Zero — the function schema is the contract, generated from signatures |
| Tokens spent per request | High (system prompt is heavy) | Low (REACT_TOOLS schema is compact) |
| Frequency of LLM errors | High — missed `WHERE`, broken `JOIN`, full table scan, hallucinated columns | Near zero — only fills typed args |
| Safety surface | SQL injection, `DROP TABLE`, runaway queries | Zero — the LLM never produces SQL |
| Debuggability of a bad answer | Forensic — read the prompt, the schema, the generated SQL, and reconstruct the LLM's reasoning | Trivial — one log line shows which function was called with what args |
| Cost of adding a new capability | Edit the system prompt → risk of regressing other queries → re-test everything | Add a new function → zero blast radius |
| Cacheability | Hard (same intent → different SQL → no key match) | Easy (`(name, args)` is a clean cache key) |
| Whether your SOP can mandate it | No — SOPs can't pin down which SQL strings the model will emit | Yes — SOP can write `tool: list_lots, args: {...}` directly |

The unintuitive part is the *prompt cost*. A generic SQL executor doesn't work without telling the LLM about your tables. That means a schema dump — typically 500–2000 tokens of CREATE TABLE statements and example queries — in every system prompt, in every request. Typed functions push that schema into native tool definitions, which are far more compact and far better understood by the model.

---

## "But typed functions feel like a lot of code"

This is the most common pushback, and it's almost always wrong, because people mistake *enumeration of patterns* for *enumeration of queries*. They are different.

Naive typed approach (don't do this):

```
list_lots_by_week()
list_lots_by_product()
list_lots_by_week_and_yield()
list_lots_by_product_and_yield()
...
```

This is the combinatorial explosion that scares people away from typed functions. But the right answer is parameterized typed functions:

```python
def list_lots(
    week=None, product=None, min_yield=0, max_yield=100,
    order_by="yield", limit=50,
):
    ...
```

One function with optional filters covers every combination above. The LLM just leaves unused filters as `None`.

For a wafer yield agent, the entire data-access surface tends to collapse into five or six functions:

| Function | Covers |
|---|---|
| `list_lots(...)` | "list / filter / sort lots" — by any combo of filters |
| `get_lot_detail(lot_id)` | "show me everything about this one lot" |
| `list_products()` | "what products are even in the data" |
| `get_yield_trend(product, time_range)` | "how is this product trending" |
| `compare_lots(lot_ids[])` | "show A vs B vs C side-by-side" |
| `find_similar_lots(reference_lot, top_k)` | "give me lots like this one" (edges into RAG territory) |

Five or six functions, 600–900 lines of Python, written once. That's it.

---

## Why engineering environments tilt so hard toward typed

A pattern I keep coming back to: **the value of generic SQL is "unlimited ad-hoc exploration", and that is not the engineering workflow**.

Engineering tasks are SOP-driven. The questions an engineer asks repeat:

- list
- find one
- compare
- trend
- find similar

These five verbs cover ~99% of the structured-data interactions a wafer yield engineer needs. An LLM that "can write any SQL" is solving a problem that doesn't exist. Worse, it solves it unreliably (different runs → different SQL → different results → impossible to reproduce or audit).

Typed functions are an *enumeration* of the agent's data-access vocabulary. That enumeration matches the SOP-driven philosophy:

- Senior engineers define what queries exist (by writing functions).
- The SOP can mandate the order in which they run.
- The LLM only chooses *which* of the available functions to call, and *what parameters* to fill — never *what query to run*.

This is the same shift in framing that takes "let the LLM write code" (a research idea) to "let the LLM fill parameters" (the production reality at OpenAI, Anthropic, and every serious tool-using agent). The industry has converged on parameter-filling for a reason.

---

## The one place generic SQL has a real edge — and even then

True ad-hoc data exploration ("show me anything", data-science notebook style) is the only honest use case for generic SQL with an LLM. Even there, the typical answer in 2026 is not "give the LLM raw SQL", it's:

- a **constrained query language** (e.g., a JSON DSL the LLM emits, which the backend parses), or
- a **pre-vetted query library** the LLM picks from by name:

```python
def execute_predefined_query(query_name: str, params: dict):
    if query_name not in ALLOWED_QUERIES:
        raise ValueError(...)
    return ALLOWED_QUERIES[query_name](**params)
```

Both are still typed in spirit — the LLM is choosing from an enumerated set, not generating raw code. Raw SQL generation by the LLM remains a bad idea in production, even in ad-hoc environments, because the failure modes (security, reliability, cost) are too severe.

---

## The takeaway

For engineering LLM agents, the answer is unambiguous:

1. **Use typed functions.** Not text-to-SQL.
2. **Use parameters, not multiplication.** One `list_lots(...)` with optional filters, not ten `list_lots_by_*()`.
3. **Start with five or six functions** that cover the common verbs (list, find, compare, trend, similar). Add more only when the LLM repeatedly tries to do something none of them cover.
4. **Treat the function set as part of the SOP**, not a separate concern. Senior engineers own which queries exist; the LLM only fills parameters.

The deeper principle: **the LLM is good at understanding intent and bad at writing code**. Design every external-facing surface to play to the first strength and avoid the second. Typed functions do that. Generic SQL doesn't.

This is the entire reason OpenAI Function Calling, Anthropic Tool Use, and the MCP protocol itself are built around typed schemas, not around "send the model a code execution sandbox". The architecture is the lesson.
