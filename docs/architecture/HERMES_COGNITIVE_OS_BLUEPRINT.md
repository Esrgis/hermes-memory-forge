# Hermes Cognitive OS Blueprint

This is the canonical architecture document for the Hermes Memory Forge direction.

Hermes should not become one giant autonomous agent or one endless chat session.
The target is a local-first personal cognitive operating system: a persistent assistant runtime that coordinates memory, retrieval, workflows, tools, and eventually scoped multi-agent execution.

## 1. Core Thesis

Chat sessions are disposable.

Memory, architecture, and workflow state are persistent.

The correct direction is:

```text
stateless LLM/runtime sessions
+ persistent memory
+ bounded retrieval
+ reflection
+ blackboard state
+ orchestration
+ tool execution
```

The app should not reinvent every subsystem. It should coordinate existing tools cleanly:

- Hermes for identity, assistant UX, tool access, and memory coordination
- Obsidian for semantic markdown memory
- SQLite for runtime state and blackboard records
- n8n or small scripts for automation
- Telegram/Discord/CLI/dashboard for interaction
- OpenRouter/Codex/Ollama/LiteLLM for model routing
- Codex CLI and terminal workflows for execution
- GitHub for project distribution and collaboration

## 2. Layered Architecture

```text
External Sources
    ↓
Automation / Perception Layer
    ↓
Blackboard Runtime
    ↓
Reflection + Distillation
    ↓
Episodic Memory
    ↓
Semantic Memory
    ↓
Identity / Preference Memory
    ↓
Retrieval + Context Injection
    ↓
LLM Runtime
    ↓
Tools / Messaging / Dashboard
```

### Layer 1: Interfaces

User-facing surfaces:

- CLI/TUI
- Telegram
- Discord
- dashboard
- future mobile/voice interfaces

The dashboard should be a control and observability layer, not the brain.

It should show:

- active agents
- pending tasks
- blackboard state
- daily briefing
- recent events
- memory updates
- workflow health
- logs
- token/API usage

### Layer 2: Automation / Perception

Purpose:

- cron jobs
- webhooks
- API fetching
- notifications
- repetitive workflows

Possible implementation:

- n8n for visual/API automation
- PowerShell scripts for deterministic local actions
- Hermes cron only after routes are proven safe

This layer should fetch facts and inject structured events. It should not become the brain.

Examples:

- weather update
- calendar pull
- RSS/news fetch
- finance ticker update
- task carry-over check
- service health check

### Layer 3: Blackboard Runtime

The blackboard is working memory and coordination state.

Use:

- SQLite first
- SQLite FTS5 for search
- JSON append logs for simple experiments
- Redis/NATS/RabbitMQ only later if event volume demands it

Blackboard tables may include:

- `tasks`
- `events`
- `suggestions`
- `agent_outputs`
- `decisions`
- `memory_candidates`
- `agent_status`
- `permissions`
- `workflow_runs`

Obsidian must not be the blackboard. It is not a task queue, concurrent state engine, or high-frequency event bus.

### Layer 4: Obsidian Semantic Memory

Obsidian is long-term semantic persistence:

- stable knowledge
- distilled reflections
- searchable history
- project specs
- environment docs
- known failure patterns

Suggested vault:

```text
Vault/
├── Daily/
├── Projects/
├── Concepts/
├── Memory/
├── Specs/
├── System/
│   └── Assistant/
├── Snippets/
├── People/
└── Inbox/
```

Obsidian is an active semantic substrate, not a markdown graveyard.
Hermes should read, re-distill, merge, refactor, and promote patterns over time.

## 3. Memory Model

Memory strength is not "store everything".

Memory strength is "compress correctly and retrieve the right thing".

### Tier 1: Hot Memory

Injected into routine sessions.

Contains:

- active tasks
- recent corrections
- communication preferences
- procedural quirks
- current constraints

Keep compact. Promote stable entries when it approaches capacity.

### Tier 2: Semantic Vault Files

Stable reference, read on demand.

Contains:

- workflows
- environment
- preferences
- operational patterns
- architecture principles
- known failure modes

### Tier 3: Episodic Timeline

Daily notes are not diaries.

They are:

- event stream
- audit log
- operational history
- retrieval anchor

Use daily notes to reconstruct context, then distill recurring patterns into semantic files.

### Compression Path

```text
specific events
↓
patterns
↓
principles
↓
identity / workflow memory
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

## 4. Reflection Pipeline

Correct flow:

```text
conversation
→ reflection
→ distillation
→ structured memory
→ retrieval
→ selective context injection
```

Do not write raw chat logs as permanent memory.

Reflection should produce:

- daily summaries
- memory candidates
- issue/fix records
- stable preference updates
- workflow improvements
- stale/conflicting-memory flags

## 5. Agent Classes

The bottleneck is not the number of agents.

The bottleneck is:

- orchestration
- context routing
- dependency management
- integration correctness
- memory consistency
- permissions

### Advisory Agents

Cheap/free agents behave like lightweight advisors.

They may:

- observe
- summarize
- recommend
- notify

Examples:

- weather reminders
- laundry suggestions
- unfinished task reminders
- finance alerts
- daily briefings
- news summaries

They must not:

- deploy code
- modify important files
- rewrite system memory
- perform dangerous actions
- execute privileged operations

### Executive Agents

Executive agents perform real work.

Examples:

- coding agent
- planner agent
- reviewer
- integrator
- memory agent
- research agent

They require:

- scoped context
- permission levels
- bounded autonomy
- blackboard task records
- output review

## 6. Permission Model

```text
Level 0 — Observer
  read public APIs only
  no memory writes
  no tools

Level 1 — Advisor
  create suggestions
  write lightweight notifications

Level 2 — Assistant
  read blackboard
  create notes/tasks
  limited vault access

Level 3 — Worker
  execute tools
  modify scoped workspace
  run scripts

Level 4 — Operator
  deploy systems
  modify infrastructure
  dangerous operations
  requires confirmation
```

Default routine agents should stay at Level 0-2.

## 7. Event-Driven Runtime

Agents should not run continuously.

```text
no task
→ sleep

event/task detected
→ wake only relevant agent(s)
```

Examples:

```text
weather_update
→ household advisor wakes

task_overdue
→ scheduler advisor wakes

repo_task_created
→ project manager creates scoped worker tasks

memory_candidate_ready
→ memory agent reviews for promotion
```

This reduces token usage, API cost, and coordination noise.

## 8. Team Topology

Agents should be domain-specialized. They should not all see the whole project.

Potential teams:

- Daily Advisory Team: weather, reminders, schedule, news
- Scheduler Team: calendar, overdue tasks, carry-over logic
- Coding Team: project manager, planner, workers, reviewer, integrator
- Memory Team: summarize logs, consolidate memory, archive stale notes
- Research Team: bounded research, source summaries, relevance classification
- Household Team: lightweight local-life suggestions

### Coding Team Flow

```text
User request
↓
Project Manager
↓
Blackboard tasks
↓
Workers claim scoped tasks
↓
Reviewer checks outputs
↓
Integrator merges
↓
Memory Agent records durable lessons
```

## 9. Daily Advisory System

Purpose:

- weather reminders
- news summaries
- schedule awareness
- task carry-over
- lightweight suggestions

Inputs:

- weather APIs
- RSS/news
- calendar
- unfinished tasks
- daily note state

Output:

- daily brief
- Telegram/Discord notification
- daily note update

Rules:

- Do not auto-complete tasks.
- Do not modify important files.
- Do not use strong/costly models unless explicitly needed.
- Log events to daily note.

Task states:

- `planned`
- `missed`
- `carried_over`
- `cancelled`
- `done`

## 10. Model Routing

Models are replaceable compute backends.

Architecture matters more than any single model.

Correct hierarchy:

```text
workflow > model
memory > model
retrieval > model
architecture > model
```

Routing policy:

- cheap/free model for routine suggestions
- strong model for coding and integration
- local model for private/simple offline work
- fallback provider for resilience

Possible stack:

- OpenRouter
- OpenAI Codex
- Ollama
- LiteLLM

## 11. MVP Roadmap

### Phase 1: Stable Hermes Runtime

Build:

- CLI/TUI usability
- Telegram quick routes
- bounded tool routing
- Obsidian vault scaffold
- daily note script
- memory pipeline docs
- issue/fix log

Avoid:

- swarms
- broad autonomous search
- dashboard-first complexity
- fully autonomous agents

### Phase 2: Blackboard Runtime

Add:

- SQLite task table
- event log
- suggestions table
- memory candidates table
- simple worker registration
- basic status commands

### Phase 3: Reflection and Distillation

Add:

- daily summary
- weekly synthesis
- memory promotion
- stale memory review
- issue/fix consolidation

### Phase 4: Controlled Multi-Agent

Introduce:

- Daily Advisory Team
- Memory Team
- Coding Team
- Research Team

Keep permissions scoped and measurable.

### Phase 5: Dashboard

Build only after runtime contracts are stable.

Dashboard should observe and control:

- tasks
- agents
- memory candidates
- event logs
- token/tool usage
- workflow health

## 12. Known Risks

Multi-agent systems can become:

- coordination hell
- token explosions
- recursive loops
- context conflicts
- duplicated work
- unsafe tool execution
- noisy memory

Mitigations:

- single-agent stability first
- bounded routes
- scoped context
- explicit permissions
- blackboard task records
- append-only event logs
- review before integration
- no broad search without approval

## 13. Unsolved Research Problems

Still missing:

- memory decay
- semantic consolidation
- conflict resolution
- event storm protection
- agent trust/safety
- retrieval discipline
- agent lifecycle
- reflection quality control
- dashboard UX
- stale belief demotion

These are research targets, not Phase 1 requirements.

## 14. Final Design Position

Hermes should become:

- identity layer
- memory manager
- orchestrator
- primary assistant interface

Hermes should not become:

- the only worker agent
- the runtime database
- the entire automation system
- a giant autonomous AGI

The project is evolving from chatbot engineering toward practical cognitive systems engineering.

Relevant domains:

- operating systems
- distributed systems
- workflow engines
- retrieval systems
- knowledge architecture
- orchestration systems
