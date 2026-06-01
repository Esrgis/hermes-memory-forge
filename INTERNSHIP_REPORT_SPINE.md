# Internship Report Spine: Hermes Multi-Agent Research Path

Muc dich file nay: gom lai "loi di chinh" cua bao cao thuc tap de de doc, de check, va de tiep tuc viet thanh bao cao chinh thuc.

## 1. Huong nghien cuu chinh

Huong nghien cuu chinh la tim hieu AI Agent, sau do thu hep vao Multi-Agent System cho bai toan dieu phoi cong viec, local automation, memory, tool usage va human approval.

Mach tong quat:

```text
AI Agent
-> gioi han cua single-agent
-> Paperclip / OpenClaw
-> van de runtime, setup, control, debug
-> CrewAI role-based multi-agent
-> dieu phoi song song
-> blackboard / shared state
-> can PM agent
-> Hermes Guild architecture
```

## 2. Buoc 1: AI Agent

Noi dung can viet:

- Agent la mot he thong co the nhan input, suy luan, dung tool, ghi nho va tao output.
- Cac thanh phan co ban: perception, reasoning, memory, action, tools.
- Agent don le co the xu ly task ngan, nhung de mat kiem soat khi task dai, nhieu file, nhieu trang thai, nhieu lan retry.

Nhan dinh chinh:

```text
Van de khong chi la lam cho agent thong minh hon.
Van de lon hon la dieu phoi, trang thai, memory, tool boundary va kha nang debug.
```

## 3. Buoc 2: Thu Paperclip / OpenClaw

Muc tieu:

- Khao sat mot agent runtime da co san.
- Hieu workspace, tool budget, provider, autonomy mode, memory provider, task execution.
- Xem cach mot he thong agent dung tool va tu van hanh workflow.

Ket qua hoc duoc:

- Agent runtime can workspace ro rang.
- Tool calling phai co gioi han.
- Provider/adapter la diem rat de loi.
- Local setup tren Windows/WSL/Docker/Podman rat anh huong den do on dinh.

Van de gap phai:

- Setup phuc tap.
- Loi moi truong, permission, NTFS/Ext4, container lifecycle.
- Kho debug khi runtime, adapter va agent logic bi tron vao nhau.
- Chua giai quyet tot nhu cau local-first, nho gon, de quan sat.

Ket luan:

```text
Paperclip/OpenClaw huu ich de hieu agent runtime,
nhung chua phai loi giai phu hop cho he thong Hermes hien tai.
```

## 4. Buoc 3: Chuyen sang CrewAI

Muc tieu:

- Tim hieu multi-agent theo vai tro: researcher, writer, reviewer, manager.
- Hieu task delegation, tool declaration, knowledge/RAG, sequential/hierarchical process.

Ket qua hoc duoc:

- Chia vai giup workflow de ly giai hon.
- Agent nen co role, goal, tool va output contract ro.
- Knowledge/RAG co ich cho style consistency va project memory.

Van de nhan ra:

- Multi-agent khong tu dong tot hon single-agent.
- Neu khong co state va stop condition, se ton token va lap vong.
- Framework giai quyet mot phan abstraction, nhung khong thay the workflow design.

Ket luan:

```text
CrewAI giup hieu role-based multi-agent,
nhung bai toan that su nam o orchestration va state management.
```

## 5. Buoc 4: Dieu phoi song song

Muc tieu:

- Tim hieu cach chay nhieu task/agent cung luc.
- Khao sat timeout, cancel, retry, fail state, QA loop.

Nhan dinh:

- Parallel chi co loi khi task doc lap va output co contract.
- Can gioi han so vong lap.
- Can co trang thai ro: pending, running, blocked, failed, done.
- Can tranh viec nhieu agent cung ghi vao mot noi khong kiem soat.

Ket luan:

```text
Song song khong phai la spawn that nhieu agent.
Song song can queue, lock, contract va co che dung.
```

## 6. Buoc 5: Blackboard / Shared State

Ly do can blackboard:

- Agent can noi chung de doc task, claim viec, ghi ket qua, ghi loi.
- Human/user can xem trang thai workflow.
- Runtime state khong nen tron vao Obsidian memory.

Thanh phan nen co:

- SQLite cho runtime state.
- Bang task/job/artifact/event.
- Single-writer hoac API/script trung gian de tranh lock va xung dot.
- Obsidian chi luu memory da tom tat, khong luu raw runtime.

Ket luan:

```text
Blackboard la buoc chuyen tu "agent thong minh" sang "he thong co trang thai".
```

## 7. Buoc 6: Can PM Agent

Ly do:

- Khi co nhieu worker/task, can mot vai tro dieu phoi.
- PM agent quyet dinh chia viec, review output, retry, escalate, hoi user.

PM agent nen lam:

- Lap ke hoach.
- Chia task.
- Kiem tra artifact.
- Tong hop trang thai.
- Goi human approval khi can.

PM agent khong nen lam:

- Khong lam moi viec thay worker.
- Khong tu tao vo han sub-agent.
- Khong nam giu runtime state bang chat context.

Ket luan:

```text
PM agent la lop reasoning/governance,
khong phai scheduler hay database.
```

## 8. Buoc 7: Hermes Guild Model

Mo hinh Guild gom cac vai tro:

- Hermes: PM/guild master, reasoning, synthesis, decision, memory-aware assistant.
- Flock: candidate worker runtime cho typed multi-agent/blackboard orchestration.
- n8n: scheduler, cron, queue trigger, Telegram notification, workflow orchestration don gian.
- SQLite: runtime blackboard/state.
- Obsidian: long-term semantic memory.
- Codex: coding/workspace execution agent.

Ranh gioi quan trong:

```text
n8n = deterministic workflow / trigger / notification
Hermes = reasoning / decision / memory / synthesis
SQLite = runtime state
Obsidian = distilled long-term memory
Flock = future worker-team runtime khi can typed multi-agent
```

## 9. Cau chuyen bao cao nen viet

Doan tom tat co the dung:

```text
Qua qua trinh thuc nghiem, trong tam nghien cuu chuyen tu viec "tim mot agent framework manh"
sang viec thiet ke mot he thong AI agent co kha nang dieu phoi, quan sat, ghi nho va kiem soat.

Paperclip/OpenClaw giup nhan dien cac thanh phan cua agent runtime nhung gap nhieu van de ve setup,
adapter va debug trong moi truong local. CrewAI giup lam ro mo hinh multi-agent theo vai tro,
nhung cung cho thay neu thieu state, queue va stop condition thi multi-agent de tro thanh ton token
va kho kiem soat.

Tu do, kien truc Hermes Guild duoc de xuat: Hermes phu trach reasoning va decision, n8n phu trach
scheduler va notification, SQLite luu runtime state, Obsidian luu memory dai han, va Flock duoc xem
nhu huong mo rong cho worker runtime khi can multi-agent that su.
```

## 10. Diem can tranh khi viet bao cao

- Khong viet nhu minh "build thanh cong tat ca".
- Khong noi multi-agent luon tot hon single-agent.
- Khong de metaphor Guild che mat kien truc that.
- Khong copy bao cao cua nguoi khac.
- Khong dua qua nhieu ten framework ma khong noi duoc bai hoc.
- Khong tron runtime state voi long-term memory.
- Khong bien Hermes thanh mot hive mind qua phuc tap.

## 11. Buoc tiep theo

Truoc khi code tiep, nen lam 3 viec:

1. Bien file nay thanh muc luc bao cao thuc tap.
2. Gan moi giai doan voi bang timeline ngay/thang va artifact da test.
3. Bo sung citation chinh thuc cho AI Agent, Multi-Agent System, RAG, CrewAI, n8n, SQLite, Obsidian/local-first workflow.
