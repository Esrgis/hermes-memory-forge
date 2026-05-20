# Memory Pipeline

Hermes should not store everything it sees. Memory must be distilled.

Preferred flow:

```text
conversation
-> reflection
-> distillation
-> structured memory
-> retrieval
-> selective context injection
```

## Three-Tier Memory

Memory is semantic compression, not raw storage. See `docs/architecture/COGNITIVE_ARCHITECTURE.md` for the broader direction.

### Tier 1: Hot Memory

Injected into routine sessions.

- Keep compact.
- Store active projects, recent corrections, communication preferences, and procedural quirks.
- Target size: under 6000 characters.
- When it reaches roughly 67% capacity, promote stable entries into vault living files.

### Tier 2: Vault Living Files

Stable reference files read on demand.

- Store environment facts, operational context, known failure patterns, and durable workflow rules.
- Keep them organized by topic, not by conversation.
- Update them when a pattern becomes stable across multiple sessions.
- Retrieve them through bounded file reads or the local Obsidian FTS index before considering vector RAG.

### Tier 3: Daily Notes

Searchable timeline.

- Create one dated note per day.
- Log decisions, fixes, events, and wins.
- Daily notes are append-only.
- Weekly/monthly summaries should consolidate daily notes into higher-level semantic memory.

Compression path:

```text
raw events
-> daily summaries
-> recurring patterns
-> stable principles
-> identity/workflow memory
```

Example:

```text
Raw: User repeatedly rejects recursive filesystem crawling.
Compressed: User prefers bounded retrieval workflows.
```

Storage roles:

- Obsidian vault: long-term source of truth, written as clean markdown notes.
- Hermes `memories/`: small distilled facts about the user, preferences, and durable assistant context.
- `_runtime/`: temporary workspace state, experiment notes, command outputs, and scratch records.
- `sessions/`: Hermes session history, not a knowledge base.

Do not store:

- raw terminal dumps
- secrets
- auth tokens
- unreviewed chat transcripts
- full vault context in a single prompt

Good memory candidates:

- stable user preferences
- architecture decisions
- project paths
- current operating rules
- distilled daily summaries
- durable lessons from debugging

Bad memory candidates:

- every command from a session
- every phrasing detail from a conversation
- transient errors that will not recur
- duplicate facts already stored in living files
- stale project state

Obsidian write policy:

- `Daily/`: date-based summaries and work logs.
- `Projects/`: project-specific specs and plans.
- `Concepts/`: reusable technical concepts.
- `Memory/`: durable distilled assistant/user memory.
- `Runtime/`: only if intentionally visible in the vault; otherwise prefer workspace `_runtime/`.

## Routing Rules

When the user says "log it" or "save it", route by type:

- Operational events, meetings, calls, and decisions -> today's daily note `## Log`
- System issues and technical fixes -> `System/Assistant/logs/issues-fixes-log.md`
- Learned corrections and preferences -> hot memory first; promote to vault if stable
- Recurring workflows -> procedure file or skill after the workflow proves repeated
- Unknown incoming material -> `Inbox/` until classified

Do not write raw chat transcripts into the vault.

## Recall And RAG MVP

The first retrieval layer for Obsidian should be local SQLite FTS5, not embeddings.

Canonical retrieval protocol:

```text
D:\HermesGuildCore\_obsidian_vault\Specs\Memory Query Protocol Spec.md
```

Use that spec for source tiers, query packets, session-history fallback, metadata repair, and cleanup rules.

Flow:

```text
Obsidian markdown
-> heading/file chunks
-> SQLite FTS5 index outside the vault
-> snippet/path results
-> selective file read
-> optional Hermes reasoning
```

Rules:

- Keep the index outside Obsidian, such as `%LOCALAPPDATA%\hermes\blackboard\obsidian_memory_index.sqlite`.
- Do not index secrets, auth files, `.obsidian`, generated folders, or raw chat logs.
- Return snippets and paths first; read full notes only when needed.
- Treat session history as fallback evidence, not the durable memory layer.
- If recall succeeds only after session-history search, repair the durable note metadata or aliases when memory repair is allowed.
- Use vector embeddings later only if FTS recall is not good enough.

Current script:

```powershell
python .\scripts\obsidian-memory-index.py build --vault-path D:\Path\To\MemoryCore
python .\scripts\obsidian-memory-index.py search "query"

powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-obsidian-memory-index.ps1 -VaultPath D:\Path\To\MemoryCore
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\search-obsidian-memory.ps1 -Query "query"
```

## Mutation Guard

Investigation or recall jobs may report findings, create suggestions, or add memory candidates. They must not delete hot memory, delete blackboard tasks, rewrite durable memory, or modify cron/gateway state unless the user explicitly approved that mutation.

## Open Problems

The current three-tier setup is infrastructure, not a complete cognitive architecture.

Still unsolved:

- abstraction hierarchy
- semantic consolidation
- dynamic attention
- orchestration scaling
- memory conflict resolution
- stale belief decay

Treat these as research targets after the basic Hermes/Obsidian workflow is reliable.
