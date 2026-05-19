# Cognitive Architecture Direction

This project is not just a chatbot, AI wrapper, or second-brain note system.

The long-term direction is a local-first personal cognitive operating system:

- persistent assistant infrastructure
- disciplined retrieval
- memory hierarchy
- semantic compression
- blackboard runtime
- reflection pipeline
- eventual orchestration

## Core Thesis

Memory is not a database.

A database stores records. Memory performs:

- abstraction
- prioritization
- retrieval
- forgetting
- synthesis
- conflict resolution

The useful assistant does not remember everything. It compresses correctly.

## Memory Layers

```text
External Sources
        ↓
Perception Layer
        ↓
Blackboard Runtime
        ↓
Reflection Engine
        ↓
Episodic Layer
Daily logs, events, audit trail
        ↓ distillation
Semantic Layer
Principles, patterns, known failure modes
        ↓ stabilization
Identity Layer
Values, preferences, stable workflows
        ↓ retrieval
Context Injection
        ↓
LLM Runtime
```

## Obsidian Role

Obsidian is not a magic AI notebook.

It is a local markdown substrate:

- human-readable
- AI-readable
- grep-friendly
- versionable
- durable across tool/framework changes

The vault should be an active semantic substrate, not a markdown graveyard.

Hermes should read, re-distill, merge, refactor, and promote patterns from the vault over time.

## Daily Notes

Daily notes are not diaries.

They are an event stream:

- timeline
- audit log
- operational history
- retrieval anchor

Daily notes are useful because they let the assistant reconstruct context later:

```text
"When did we debug the Hermes Telegram route?"
→ search Daily/
→ find timestamped event
→ reconstruct fix and related files
```

But daily notes must not become infinite noise. They need summarization layers:

- daily event log
- weekly synthesis
- monthly abstraction
- topic clustering
- promotion into semantic memory

## Compression Path

```text
specific events
↓
patterns
↓
principles
↓
identity/workflow memory
```

Example:

```text
Raw:
User repeatedly rejects recursive filesystem crawling.

Semantic:
User prefers bounded retrieval workflows.

Identity/workflow:
Default to bounded discovery, ask before broad search, avoid generated folders.
```

## Gaps To Solve Beyond Basic Three-Tier Memory

The common Obsidian assistant pattern solves:

- organization
- persistence
- automation
- retrieval discipline

It does not fully solve:

- abstraction hierarchy
- semantic consolidation
- dynamic attention
- orchestration scaling
- memory conflict resolution
- stale belief decay

These are future Hermes research targets.

## Memory Decay

Useful memory should change over time.

Needed mechanisms:

- confidence scoring
- retrieval frequency tracking
- semantic aging
- contradiction resolution
- stale fact demotion
- reinforcement of active patterns

Old logs and sessions can be cold archived. Stable principles should survive.

## Practical Near-Term Rule

Do not build the whole cognitive architecture first.

Build in this order:

1. Reliable CLI usability.
2. Bounded tool routes.
3. Obsidian daily note and living file scaffolding.
4. Daily logging scripts.
5. Reflection and summary scripts.
6. Promotion from daily notes to semantic memory.
7. Conflict/staleness handling.
8. Blackboard runtime.
9. Multi-agent orchestration.

