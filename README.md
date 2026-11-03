# Placement Preparation Agent
### 21CSE525T — Agent Technology · 10-Assignment Submission Package

An autonomous AI agent that guides an engineering student through the campus placement cycle. Every assignment is a standalone runnable file; Assignment 5.2 integrates all of them into one system.

**Requirements:** Python 3.8+ only. No pip installs needed (standard library only). Assignment 4.2 uses live REST APIs but falls back to cached payloads if offline.

---

## Directory Layout

```
placement_agent/
├── README.md
└── assignments/
    ├── a1_1/  Assignment_1_1_Design_Specification.docx   ← Unit 1: PEAS design doc
    │          Assignment_1_1_Design_Specification.pdf
    ├── a1_2/  reflex_agent.py                            ← Unit 1: reflex rule engine
    ├── a2_1/  concurrent_agent.py                        ← Unit 2: daemon threads
    ├── a2_2/  agent_b_server.py  agent_a_client.py       ← Unit 2: sockets
    ├── a3_1/  negotiation.py                             ← Unit 3: contract net
    ├── a3_2/  utility_optimizer.py                       ← Unit 3: utility optimization
    ├── a4_1/  bdi_agent.py                               ← Unit 4: BDI architecture
    ├── a4_2/  knowledge_api_agent.py                     ← Unit 4: ontology + REST API
    ├── a5_1/  secure_agent.py                            ← Unit 5: crypto authentication
    └── a5_2/  capstone_agent.py                          ← Unit 5: full integration
```

---

## How To Run Each Assignment

| # | Command | What to show the evaluator |
|---|---------|----------------------------|
| **1.1** | (submit the PDF) | PEAS table, environment classification, 9-row agent-vs-object contrast |
| **1.2** | `cd assignments/a1_2 && python reflex_agent.py` | 12 percepts parsed, 6 condition-action rules firing, `execution_log.txt` written |
| **2.1** | `cd assignments/a2_1 && python concurrent_agent.py` | 4 daemon threads, main event loop stays responsive, latency report, no race conditions |
| **2.2** | **Terminal 1:** `python agent_b_server.py`<br>**Terminal 2:** `python agent_a_client.py` | Dual-terminal handshake, JSON state transfer over TCP, autonomous remote reaction |
| **3.1** | `cd assignments/a3_1 && python negotiation.py` | CFP broadcast, 3 rounds of counter-proposals, utility-driven concession, consensus handshake |
| **3.2** | `cd assignments/a3_2 && python utility_optimizer.py` | 10 options → constraint filter → argmax U proof → knapsack extension → 4 boundary tests |
| **4.1** | `cd assignments/a4_1 && python bdi_agent.py` | Belief/Desire/Intention separation, then a belief change forcing a mid-execution intention shift |
| **4.2** | `cd assignments/a4_2 && python knowledge_api_agent.py`<br>(offline: add `--offline`) | Ontology graph + inference queries, live GitHub/Open-Meteo calls, plan mutating from live data |
| **5.1** | `cd assignments/a5_1 && python secure_agent.py` | 2 legitimate commands pass all 6 gates; 8 attacks blocked; audit log |
| **5.2** | `cd assignments/a5_2 && python capstone_agent.py --cycles 8` | All 5 units live in one loop, CLI dashboard, final system report |

---

## Assignment Detail

### 1.1 — Project Ideation, Environment Modeling, PEAS Matrix
Design specification document. Contains the domain definition and agent persona, the full PEAS profile, a 7-dimension environment classification (partially observable, stochastic, sequential, dynamic, discrete, multi-agent, known) with justifications, a 9-criterion structural contrast between an autonomous agent and a standard OO program, and the architecture overview.

### 1.2 — Rule-Based Environmental Reasoner
Simple reflex agent. A mock telemetry generator emits percepts (topic, coding score, aptitude score, hours studied, days to placement, mock rating). `parse_percept()` normalises raw telemetry into abstracted state predicates. Six priority-ordered condition-action rules fire against that state. Writes `execution_log.txt`.

### 2.1 — Concurrent Task Daemonization
Three producer daemons (coding platform poller, placement calendar poller, aptitude sync) push onto a `queue.Queue`. A consumer thread mutates shared state inside a `threading.Lock` critical section. The main event loop prints a snapshot every 0.7s to prove it is never blocked. Ends with a clean shutdown via `threading.Event` and a per-thread latency report.

### 2.2 — Distributed Agent Messaging
Agent-A (Student Prep Agent, client) and Agent-B (Placement Cell Agent, server) over raw TCP sockets. Uses 4-byte big-endian length-prefixed framing so JSON messages never fragment. Four message intents: HANDSHAKE, SYNC_STATE, REQUEST_ACTION, TERMINATE. Agent-B reasons over the received profile against its company database and returns an eligibility report; Agent-A autonomously reacts by requesting remedial action.

### 3.1 — Multi-Agent Coordination Protocol
Contract Net Protocol. One manager (StudentPrepAgent) issues a CFP for mock-interview slots to three self-interested MentorAgents. Each mentor has a private reservation price and concession rate; the manager has weighted buyer utility `0.45·cost + 0.35·quality + 0.20·slots`. Multi-turn loop where both sides concede until the top bid clears the acceptance threshold, then a three-way handshake awards the contract and rejects the losers.

### 3.2 — Self-Interested Utility Optimization
Explicit utility function over five normalised attributes plus a redundancy penalty for topics already mastered. Hard constraints (budget, hours, minimum mentor rating) prune the 10 options to a feasible set; exhaustive search then proves optimality. Includes a knapsack extension for multi-select bundles and four boundary-resilience tests (zero budget, zero hours, impossible rating, negative budget) that return `NO_VIABLE_PLAN` instead of crashing.

### 4.1 — BDI Goal-Driven Modeling
Three separated classes: `BeliefBase` (revisable knowledge with change listeners), `DesireSet` (goals with trigger/satisfaction predicates and dynamic priority functions), `IntentionStack` (committed plans with a step cursor). The verification run executes `PLAN_CodingRemediation`, then an external percept revises `days_to_drive` from 45 to 3, which raises `SURVIVE_IMMINENT_DRIVE` priority to 30.0, causing the agent to drop the in-flight plan at step 3/7 and commit to `PLAN_EmergencyCram` with no human instruction.

### 4.2 — Knowledge Representation and Adaptive API Integration
An ontological graph with classes, five relation types, and individuals (11 skills, 5 companies, 5 resources). Inference queries: transitive prerequisite closure, skill-gap resolution, eligibility computation. Two live REST endpoints — GitHub Users API and Open-Meteo — each with graceful fallback. Two adaptation rules mutate the plan: GitHub repo count decides whether a portfolio task is inserted or suppressed, and live temperature/precipitation switches all tasks to `indoor-online` or `early-morning-slot`.

### 5.1 — Agent Authentication and Host Integrity
Six sequential verification gates: structural validity, host registry lookup, origin-IP integrity, HMAC-SHA256 signature (constant-time compare), replay/freshness (nonce set + 30s window), and role-based authorization. Ten scenarios run: 2 legitimate commands pass, and 8 attacks are blocked — forged signature, unknown host, tampered payload, replay, privilege escalation, IP spoofing, stale timestamp, malformed fuzz.

### 5.2 — Capstone Integration
Every module assembled into `PlacementPreparationAgent`. Each autonomous cycle runs: sense (drain the bus, verify signatures, revise beliefs) → reflex pass → deliberate → execute → render dashboard. An `intruder_daemon` continuously attacks the agent during the run to prove the security layer holds under live load. Ends with a final report attributing results to each unit.

---

## Suggested Demo Order (for your viva / 3-minute video)

1. `python assignments/a5_2/capstone_agent.py --cycles 6` — show the dashboard and final report first. This is the whole system.
2. `python assignments/a4_1/bdi_agent.py` — scroll to Phase 3/4 and point at the intention shift. This is the highest-value single moment.
3. `python assignments/a5_1/secure_agent.py` — scroll to the audit log, 8/8 attacks blocked.
4. Open two terminals for 2.2 to show real network traffic.

---

## Notes For Your Report

- Every file is commented at the top with its assignment number, objective and run command.
- Random seeds are fixed, so runs are reproducible for screenshots.
- `capstone_agent.py` uses ANSI colour. If your terminal shows escape codes, pipe through `less -R` or set the colour constants to empty strings.
- For 4.2, run it **with internet** during your demo to show live API responses; the offline flag exists only as a backup.
