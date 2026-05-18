# HERMES MULTI-AGENT ECOSYSTEM — DESIGN NOTES

## Core Direction

Hermes should NOT become:

- one omnipotent AI
- one giant autonomous AGI
- one endless chat session

Hermes should become:

- a persistent assistant runtime
- part of a broader cognitive infrastructure
- the central interface of a multi-agent ecosystem

---

# Key Insight

Chat sessions are disposable.

Memory and architecture are persistent.

Correct direction:

stateless runtime
+
persistent memory
+
retrieval
+
reflection
+
orchestration

---

# Important Distinction

## Advisory Agents

Cheap/free agents should mostly behave like:

"roommates giving suggestions"

Examples:

- weather reminders
- laundry suggestions
- unfinished task reminders
- financial alerts
- daily briefings
- news summaries

These agents SHOULD NOT:

- deploy code
- modify important files
- rewrite system memory
- perform dangerous actions
- execute privileged operations

They mostly:

- observe
- summarize
- recommend
- notify

Example:

"Looks like rain this afternoon, maybe bring clothes inside."

---

## Executive Agents

More capable agents can access:

- blackboard runtime
- tools
- workspace operations
- repositories
- memory systems

Examples:

- coding agent
- planner agent
- memory agent
- integrator agent
- research agent

These agents perform actual work.

Still requires:

- permission layers
- scoped access
- bounded autonomy

---

# Suggested Permission Layers

## Level 0 — Observer

- Read public APIs only
- No memory writes
- No tools

## Level 1 — Advisor

- Create suggestions
- Write lightweight notifications

## Level 2 — Assistant

- Read blackboard
- Create notes/tasks
- Limited vault access

## Level 3 — Worker

- Execute tools
- Modify scoped workspace
- Run scripts

## Level 4 — Operator

- Deploy systems
- Modify infrastructure
- Dangerous operations
- Requires confirmation

---

# Proposed Architecture

```txt
Boot machine
↓
Gateway/runtime starts
↓
Hermes online
↓
Blackboard runtime online
↓
Agent teams subscribe to task types
↓
Cron/event system injects jobs
↓
Workers process tasks
↓
Results written to blackboard/vault
↓
Hermes interacts with user
```

---

# Blackboard Architecture

Blackboard should NOT be Obsidian directly.

Correct flow:

```txt
Agents
↓
Blackboard Runtime
(SQLite / Redis / JSON event store)
↓
Reflection Layer
↓
Semantic Distillation
↓
Obsidian Vault
```

---

# Obsidian's Role

Obsidian is:

- semantic persistence
- long-term knowledge
- distilled memory
- searchable archive

Obsidian is NOT:

- runtime memory
- concurrent state engine
- task queue
- event bus
- high-frequency coordination layer

---

# Memory Philosophy

Correct memory flow:

```txt
specific events
↓
patterns
↓
principles
↓
identity
```

Memory strength is NOT:

"store everything"

Memory strength IS:

"compress correctly and retrieve the right thing"

---

# Three-Layer Memory Model

## Tier 1 — Hot Memory

Injected every session.

Contains:

- active tasks
- recent corrections
- procedural quirks
- current runtime state

Short-lived.

---

## Tier 2 — Semantic Vault Files

Stable knowledge:

- workflows
- environment
- preferences
- operational patterns
- architecture principles

Stored in Obsidian markdown.

---

## Tier 3 — Episodic Timeline

Daily notes:

- events
- logs
- decisions
- timestamps
- project evolution

Useful for reconstruction and retrieval.

---

# Reflection Pipeline

Correct pipeline:

```txt
conversation
→ reflection
→ distillation
→ structured memory
→ retrieval
```

Raw chat logs should NOT become permanent memory.

---

# Multi-Agent Insight

The bottleneck is NOT:

- number of agents

The real bottleneck is:

- orchestration
- context routing
- dependency management
- integration correctness
- memory consistency

---

# Important Design Principle

Many agents should NOT all work on the same task simultaneously.

Correct architecture:

domain-specialized teams.

Examples:

## News Team

- fetch RSS
- summarize
- classify relevance

## Scheduler Team

- calendar
- reminders
- overdue tasks

## Household Team

- weather-based suggestions
- habit reminders

## Coding Team

- repository tasks
- testing
- patch generation

## Memory Team

- summarize logs
- consolidate memory
- archive stale notes

---

# Important Warning

Multi-agent systems easily become:

- coordination hell
- token explosions
- recursive loops
- context conflicts
- duplicated work

Single-agent stability should come FIRST.

---

# Recommended Development Order

## Phase 1 — Hermes Runtime

Build:

- Telegram/CLI interface
- memory pipeline
- Obsidian integration
- retrieval
- cron jobs
- morning briefings
- logging
- tool execution

Avoid:

- large swarms
- distributed orchestration
- massive parallelism

---

## Phase 2 — Blackboard Runtime

Add:

- task queue
- event system
- shared runtime state
- scoped memory
- worker registration

---

## Phase 3 — Multi-Agent Expansion

Then introduce:

- News Team
- Scheduler Team
- Coding Team
- Memory Team
- Research Team

---

# Important Insight About Models

Models should become:

replaceable compute backends

Architecture matters more than any single model.

Correct hierarchy:

workflow > model
memory > model
retrieval > model
architecture > model

---

# Final Conclusion

This project is gradually evolving from:

- chatbot engineering

toward:

- cognitive systems engineering

Relevant domains:

- distributed systems
- operating systems
- workflow engines
- retrieval systems
- knowledge architecture
- orchestration systems

Hermes is evolving toward:

"a personal cognitive operating system"
