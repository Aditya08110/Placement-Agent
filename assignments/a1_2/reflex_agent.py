"""
Assignment 1.2 : Rule-Based Environmental Reasoner (Simple Reflex Agent)
Project: Placement Preparation Agent
------------------------------------------------------------------
Implements a Condition-Action rule engine that parses a mocked
telemetry stream of student performance data and emits reactive logs.
Run:  python reflex_agent.py
"""

import random
import time
from datetime import datetime

# ----------------------------------------------------------------------
# 1. SENSORS  -- mock live environmental data stream
# ----------------------------------------------------------------------
TOPICS = ["Arrays", "DP", "Graphs", "OOPS", "DBMS", "Aptitude", "OS"]


def sensor_stream(ticks=12, seed=7):
    """Mock telemetry feed: each tick is one 'percept' from the environment."""
    rng = random.Random(seed)
    for t in range(1, ticks + 1):
        yield {
            "tick": t,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "topic": rng.choice(TOPICS),
            "coding_score": rng.randint(20, 95),      # last test score  %
            "aptitude_score": rng.randint(25, 98),    # %
            "study_hours_today": round(rng.uniform(0, 6), 1),
            "days_to_placement": rng.randint(2, 60),
            "mock_interview_rating": rng.randint(1, 10),
        }


# ----------------------------------------------------------------------
# 2. PERCEPT PARSER  -- turns raw telemetry into an internal state dict
# ----------------------------------------------------------------------
def parse_percept(raw):
    """Sensory parsing logic: normalise raw telemetry into agent state."""
    state = {
        "topic": raw["topic"],
        "coding": raw["coding_score"],
        "aptitude": raw["aptitude_score"],
        "hours": raw["study_hours_today"],
        "deadline": raw["days_to_placement"],
        "interview": raw["mock_interview_rating"],
    }
    # derived (abstracted) percepts
    state["weak_coding"] = state["coding"] < 50
    state["weak_aptitude"] = state["aptitude"] < 50
    state["idle"] = state["hours"] < 1.0
    state["urgent"] = state["deadline"] <= 7
    state["interview_unready"] = state["interview"] <= 4
    state["strong"] = state["coding"] >= 85 and state["aptitude"] >= 85
    return state


# ----------------------------------------------------------------------
# 3. CONDITION-ACTION RULE BASE
#    Each rule = (priority, name, condition(state)->bool, action(state)->str)
# ----------------------------------------------------------------------
RULES = [
    (1, "R1_URGENT_REVISION",
     lambda s: s["urgent"],
     lambda s: f"ACTION: Switch to RAPID-REVISION mode ({s['deadline']} days left). "
               f"Queue top-50 must-do problems."),

    (2, "R2_CODING_REMEDIATION",
     lambda s: s["weak_coding"],
     lambda s: f"ACTION: Assign 5 EASY + 2 MEDIUM problems on '{s['topic']}' "
               f"(coding={s['coding']}%)."),

    (3, "R3_APTITUDE_DRILL",
     lambda s: s["weak_aptitude"],
     lambda s: f"ACTION: Push 30-question aptitude drill (aptitude={s['aptitude']}%)."),

    (4, "R4_MOCK_INTERVIEW",
     lambda s: s["interview_unready"],
     lambda s: f"ACTION: Schedule mock interview + communication feedback "
               f"(rating={s['interview']}/10)."),

    (5, "R5_IDLE_NUDGE",
     lambda s: s["idle"],
     lambda s: f"ACTION: Send reminder notification - only {s['hours']}h studied today."),

    (6, "R6_ADVANCE_LEVEL",
     lambda s: s["strong"],
     lambda s: f"ACTION: Unlock HARD tier on '{s['topic']}' + recommend Tier-1 companies."),
]

DEFAULT_ACTION = "ACTION: Continue current study plan (no rule fired)."


# ----------------------------------------------------------------------
# 4. THE SIMPLE REFLEX AGENT
# ----------------------------------------------------------------------
class SimpleReflexAgent:
    def __init__(self, name="PlacementPrepAgent"):
        self.name = name
        self.log = []

    def act(self, raw_percept):
        state = parse_percept(raw_percept)
        fired = [(p, n, act(state)) for p, n, cond, act in RULES if cond(state)]
        fired.sort(key=lambda x: x[0])          # priority ordering

        header = (f"[{raw_percept['timestamp']}] TICK {raw_percept['tick']:02d} | "
                  f"topic={state['topic']:<9} code={state['coding']:>3}% "
                  f"apt={state['aptitude']:>3}% hrs={state['hours']:<4} "
                  f"D-{state['deadline']:<2} mock={state['interview']}/10")
        print(header)
        self.log.append(header)

        if not fired:
            print("      -> " + DEFAULT_ACTION)
            self.log.append("      -> " + DEFAULT_ACTION)
        for pri, name, action in fired:
            line = f"      -> [{name}] {action}"
            print(line)
            self.log.append(line)
        print()
        return fired


# ----------------------------------------------------------------------
# 5. AGENT LOOP  (perceive -> match rule -> act)
# ----------------------------------------------------------------------
def main():
    print("=" * 78)
    print(" PLACEMENT PREPARATION AGENT :: SIMPLE REFLEX ARCHITECTURE (Assignment 1.2)")
    print("=" * 78 + "\n")

    agent = SimpleReflexAgent()
    total_fired = 0
    for percept in sensor_stream(ticks=12):
        total_fired += len(agent.act(percept))
        time.sleep(0.15)          # simulate a live stream

    print("=" * 78)
    print(f" RUN SUMMARY: 12 percepts processed | {total_fired} condition-action rules fired")
    print("=" * 78)

    with open("execution_log.txt", "w") as f:
        f.write("\n".join(agent.log))
    print(" Console log written to execution_log.txt")


if __name__ == "__main__":
    main()
