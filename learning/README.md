# Learning Notes

Concept-level notes written while building this codebase.

These are not implementation docs — see [ARCHITECTURE.md](../ARCHITECTURE.md) for that — but the **reasoning behind why certain design choices were made**. They are the kind of thing I wish someone had handed me when I started, so I'm writing them down for the next person (often a future me).

## Index

- **[Typed Function vs LLM-Generated SQL](typed-function-vs-llm-sql.md)**
  Why typed parameter-filling beats text-to-SQL for engineering LLM agents. Covers the hidden costs of generic SQL executors (prompt token cost, debuggability, safety, SOP-compatibility), the parameterized-function pattern that keeps the typed approach from exploding into hundreds of functions, and why engineering workflows tilt unambiguously toward typed.
