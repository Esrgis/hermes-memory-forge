# HERMES GUILD SYSTEM — DESIGN THOUGHTS & FRAMEWORK FEARS

This document exists to capture:
- the guild metaphor
- the intended multi-agent behavior
- the fear of overengineering
- the fear of rebuilding existing infrastructure
- the practical direction for Hermes

This is NOT a final architecture document.
This is a mindset and design reasoning document.

Hard v0 line for future agents:

```text
Guild Runtime v0 =
human-approved DAG
+ artifact blackboard
+ automatic claim
+ join review
+ bounded fix loops
```

This means the first real guild should not be a free-for-all task board.
Hermes drafts a DAG, the plan is reviewed before opening queues, workers claim only dependency-ready `open` tasks, and integration happens through artifacts rather than private worker chat.

---

# THE GUILD METAPHOR

The entire system currently makes the most sense when imagined as:

"a fantasy guild"

This metaphor is important because:
- it simplifies the architecture mentally
- it naturally explains task coordination
- it naturally explains permissions
- it prevents the "one god AI" mindset

---

# ROLE MAPPING

Guild Hall
= Dashboard application

Quest Board
= Blackboard task system

Guild Master
= Hermes / PM agent

Workers / Adventurers
= execution agents

Low-rank support staff
= daily automation systems

Archive Library
= Obsidian memory vault

Messengers
= Telegram / Discord

Execution tools
= terminal / Codex / scripts

---

# IMPORTANT REALIZATION

The dashboard is NOT:
"the brain"

The dashboard is:
"a control and visibility layer"

The app mostly coordinates existing systems.

This means:
Hermes is closer to:
- a coordinator
- a PM
- a runtime shell

than:
- a magical AGI entity

---

# DAILY TEAM IDEA

The Daily Team is intentionally weak.

This is important.

They exist to:
- keep the guild functioning
- generate lightweight advice
- monitor daily conditions
- reduce mental load

Examples:
- weather reminders
- laundry suggestions
- exercise timing
- calendar awareness
- basic economic/news awareness

Example output:

Today is hot until 17:00.
Good time to dry clothes between 9:00–17:00.
Exercise recommended around 19:00.

Top US news:
- ...

Top Vietnam news:
- ...

Important reminders:
- ...

---

# IMPORTANT INSIGHT

The Daily Team probably does NOT need:
- Flock
- heavy orchestration
- complex memory
- strong models
- blackboard access

n8n + APIs + lightweight summarization may already be enough.

This is an important simplification.

---

# BLACKBOARD AS QUEST BOARD

The blackboard is imagined as:

"a quest board"

Agents do NOT constantly talk to each other.

Instead:
- PM posts tasks
- workers claim tasks
- workers complete tasks
- integrator/reviewer handles merge

This is psychologically easier to understand than:
"agents endlessly chatting"

---

# TASK CLAIMING

The intended flow:

open task
→ worker claims
→ task locked
→ worker executes
→ result submitted
→ review/integration

Possible future states:
- open
- claimed
- blocked
- done
- failed

Task dependencies may exist:

Task B depends on Task A.

Dashboard should visually show:
- locked tasks
- dependency chains
- blocked quests

---

# RANKED ADVENTURER CLAIMING

The user's preferred mental model for worker contention is:

"adventurers have ranks; high-rank adventurers take high-rank quests first."

This should guide the task claiming contract.

Worker agents should have:
- `agent_id`
- `rank`
- `specialties`
- `status`

Tasks should have:
- `task_id`
- `required_rank`
- `linked_tasks`
- `status`
- `assignee_id`

Rank rules:
- A worker may only claim tasks at or below its rank.
- Higher-rank workers are preferred for higher-rank tasks.
- Hermes is not a normal queue worker; Hermes is manager / S-rank cognition / PM.
- Low-rank daily support staff should not claim high-risk project tasks.

Linked task rules:
- Some tasks belong to a linked quest chain.
- Claiming one linked task may reserve or prioritize the remaining linked tasks for the same worker.
- A linked chain should make dependencies explicit rather than relying on chat memory.
- The dashboard should show linked quests as a group, not as unrelated loose tasks.

This keeps contention understandable without inventing a complicated lockfile culture.
The fantasy model becomes the product model:

```text
Quest rank + adventurer rank + linked quest chain
-> eligible workers
-> ordered claiming
-> durable claim / lease
-> result returned to Hermes
```

---

# PARALLELISM GOAL

The purpose of the project is NOT:
"perfect AGI orchestration"

The purpose is:
"demonstrating believable parallel task coordination"

Even a simple demo where:
- multiple workers claim tasks
- tasks complete independently
- PM coordinates integration

is already enough to prove the concept.

---

# FEAR OF FRAMEWORKS

A major realization happened during CrewAI experimentation:

If everything is built from scratch:
the developer becomes responsible for:
- scheduling
- orchestration
- retries
- queues
- synchronization
- communication
- logging
- permissions
- state management
- retries
- recovery
- event routing

This is impossible for one person in a short time.

---

# IMPORTANT ENGINEERING REALIZATION

The goal is NOT:
"becoming a one-person infrastructure company"

The goal IS:
"assembling existing systems into a coherent product"

This is a critical mindset shift.

---

# WHAT SHOULD BE CUSTOM?

Custom logic should focus on:
- guild metaphor
- blackboard behavior
- memory philosophy
- dashboard UX
- PM workflow
- orchestration rules
- task contracts
- permission rules

This is:
the product identity.

---

# WHAT SHOULD NOT BE CUSTOM?

Do NOT reinvent:
- schedulers
- automation engines
- queues
- retry systems
- backend infrastructure
- authentication
- orchestration primitives

Use:
- n8n
- FastAPI
- SQLite
- Flock
- Telegram
- existing tooling

whenever possible.

---

# FEAR OF ACCIDENTAL FRAMEWORK DEVELOPMENT

One of the biggest dangers:

Starting with:
"I want a demo"

Then slowly drifting into:
"I am building my own orchestration engine"

This is dangerous because:
- infrastructure work explodes infinitely
- no visible product appears
- momentum dies
- demo never ships

---

# IMPORTANT WEEK 1 REALIZATION

The project does NOT need:
- perfect architecture
- advanced AI cognition
- autonomous AGI
- deep memory systems
- event buses
- distributed infrastructure

The project ONLY needs:
"a believable guild system demo"

---

# MINIMUM BELIEVABLE DEMO

A successful MVP may simply be:

- dashboard
- PM agent
- SQLite blackboard
- 3 workers
- task claiming
- dependency locks
- Telegram reporting
- daily briefing

This alone already demonstrates:
- orchestration
- parallelism
- coordination
- workflow design

---

# HERMES ROLE UNCERTAINTY

Hermes is still undefined.

Possible roles:
- PM only
- PM + memory manager
- identity layer
- tool executor
- primary assistant

This does NOT need to be solved immediately.

The role can evolve later.

---

# IMPORTANT SIMPLIFICATION

The Daily Team and Project Team should remain separated.

Daily Team:
- lightweight
- cheap
- mostly automation
- low permissions

Project Team:
- execution capable
- task-oriented
- blackboard aware
- permission controlled

This separation greatly reduces chaos.

---

# FINAL INSIGHT

The project should NOT attempt:
"perfect intelligence"

It should attempt:
"clean coordination"

This is much more realistic.

The project is fundamentally becoming:

"a dashboard-coordinated AI guild system"

rather than:
"a singular omniscient AI."
