"""
Assignment 4.1 : Belief-Desire-Intention (BDI) Goal-Driven Modeling
Project: Placement Preparation Agent
------------------------------------------------------------------
Three explicitly separated collections/classes:
   BeliefBase   - knowledge repository (facts about student & world)
   DesireSet    - abstract strategic goals with dynamic priority
   IntentionStack - committed procedural plans currently executing

Demonstrates DYNAMIC PLAN RECALCULATION: when a belief changes
mid-execution, the deliberation cycle drops the current intention and
re-commits to a different one.

Run:  python bdi_agent.py
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Dict, Any, Callable


def log(tag, msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [{tag:<12}] {msg}")


# ======================================================================
# 1. BELIEFS  -- the agent's knowledge base state repository
# ======================================================================
class BeliefBase:
    def __init__(self):
        self._b: Dict[str, Any] = {}
        self._listeners: List[Callable] = []
        self.revision_count = 0

    def add(self, key, value):
        self._b[key] = value

    def get(self, key, default=None):
        return self._b.get(key, default)

    def update(self, key, value, reason="percept"):
        old = self._b.get(key)
        if old == value:
            return False
        self._b[key] = value
        self.revision_count += 1
        log("BELIEF", f"REVISION #{self.revision_count}: '{key}' {old!r} -> {value!r}  ({reason})")
        for fn in self._listeners:
            fn(key, old, value)
        return True

    def on_change(self, fn):
        self._listeners.append(fn)

    def snapshot(self):
        return dict(self._b)

    def dump(self):
        print("    +-- BELIEF BASE " + "-" * 58)
        for k, v in self._b.items():
            print(f"    |   {k:<26} = {v}")
        print("    +" + "-" * 73)


# ======================================================================
# 2. DESIRES  -- abstract strategic milestones
# ======================================================================
class DesireStatus(Enum):
    INACTIVE = "INACTIVE"
    ACTIVE = "ACTIVE"
    ACHIEVED = "ACHIEVED"
    DROPPED = "DROPPED"


@dataclass
class Desire:
    name: str
    base_priority: float
    trigger: Callable[[BeliefBase], bool]      # when is this desire relevant?
    satisfied: Callable[[BeliefBase], bool]    # when is it achieved?
    urgency: Callable[[BeliefBase], float] = lambda b: 1.0
    status: DesireStatus = DesireStatus.INACTIVE

    def priority(self, beliefs):
        return round(self.base_priority * self.urgency(beliefs), 3)


class DesireSet:
    def __init__(self):
        self.desires: List[Desire] = []

    def add(self, d):
        self.desires.append(d)

    def deliberate(self, beliefs):
        """Re-evaluate which desires are active; return them priority-sorted."""
        active = []
        for d in self.desires:
            if d.satisfied(beliefs):
                if d.status != DesireStatus.ACHIEVED:
                    d.status = DesireStatus.ACHIEVED
                    log("DESIRE", f"'{d.name}' -> ACHIEVED")
                continue
            if d.trigger(beliefs):
                if d.status == DesireStatus.INACTIVE:
                    log("DESIRE", f"'{d.name}' -> ACTIVE (priority {d.priority(beliefs)})")
                d.status = DesireStatus.ACTIVE
                active.append(d)
            else:
                d.status = DesireStatus.INACTIVE
        active.sort(key=lambda d: -d.priority(beliefs))
        return active

    def dump(self, beliefs):
        print("    +-- DESIRE SET " + "-" * 59)
        for d in self.desires:
            print(f"    |   {d.name:<34} {d.status.value:<10} prio={d.priority(beliefs)}")
        print("    +" + "-" * 73)


# ======================================================================
# 3. INTENTIONS  -- committed step-by-step procedural pipelines
# ======================================================================
@dataclass
class Intention:
    desire: str
    plan_name: str
    steps: List[str]
    cursor: int = 0
    dropped: bool = False
    log_trace: List[str] = field(default_factory=list)

    def done(self):
        return self.cursor >= len(self.steps)

    def next_step(self):
        s = self.steps[self.cursor]
        self.cursor += 1
        self.log_trace.append(s)
        return s

    def progress(self):
        return f"{self.cursor}/{len(self.steps)}"


class IntentionStack:
    def __init__(self):
        self.stack: List[Intention] = []
        self.abandoned: List[Intention] = []

    def current(self):
        return self.stack[-1] if self.stack else None

    def commit(self, intention):
        self.stack.append(intention)
        log("INTENTION", f"COMMIT plan '{intention.plan_name}' for desire '{intention.desire}' "
                         f"({len(intention.steps)} steps)")

    def drop_current(self, reason):
        if self.stack:
            i = self.stack.pop()
            i.dropped = True
            self.abandoned.append(i)
            log("INTENTION", f"DROP plan '{i.plan_name}' at step {i.progress()} -- {reason}")

    def dump(self):
        print("    +-- INTENTION STACK " + "-" * 54)
        if not self.stack:
            print("    |   (empty)")
        for i in reversed(self.stack):
            print(f"    |   {i.plan_name:<32} {i.progress()} steps  desire='{i.desire}'")
        print("    +" + "-" * 73)


# ======================================================================
# 4. PLAN LIBRARY : desire -> procedural intention
# ======================================================================
PLAN_LIBRARY = {
    "MASTER_WEAK_CODING_TOPIC": ("PLAN_CodingRemediation", [
        "load weakest topic from belief base",
        "fetch 10 curated problems for that topic",
        "solve 4 EASY problems",
        "solve 4 MEDIUM problems",
        "solve 2 HARD problems",
        "re-run topic assessment test",
        "write updated coding_score belief",
    ]),
    "CLEAR_APTITUDE_CUTOFF": ("PLAN_AptitudeDrill", [
        "identify weak aptitude section",
        "run 30-question timed drill",
        "review incorrect answers",
        "run 20-question re-test",
        "write updated aptitude_score belief",
    ]),
    "ACHIEVE_INTERVIEW_READINESS": ("PLAN_InterviewPrep", [
        "generate 15 HR + 15 technical questions",
        "run STAR-format practice",
        "book mock interview slot",
        "conduct mock interview",
        "process mentor feedback",
        "write updated interview_rating belief",
    ]),
    "SURVIVE_IMMINENT_DRIVE": ("PLAN_EmergencyCram", [
        "PRIORITY OVERRIDE: freeze long-horizon plans",
        "load company-specific previous-year question bank",
        "revise top-50 must-do problems",
        "revise 1-page core CS cheat sheet",
        "rehearse 60-second self-introduction",
        "confirm drive registration + documents",
    ]),
    "BUILD_PROJECT_PORTFOLIO": ("PLAN_PortfolioBuild", [
        "select 2 resume-worthy projects",
        "push code to GitHub with README",
        "add measurable impact metrics to resume",
    ]),
}


# ======================================================================
# 5. THE BDI AGENT + DELIBERATION CYCLE
# ======================================================================
class BDIAgent:
    def __init__(self):
        self.B = BeliefBase()
        self.D = DesireSet()
        self.I = IntentionStack()
        self.belief_changed_flag = False
        self.B.on_change(lambda k, o, n: setattr(self, "belief_changed_flag", True))
        self._bootstrap()

    def _bootstrap(self):
        # ---- initial beliefs ----
        for k, v in {
            "coding_score": 42, "aptitude_score": 81, "interview_rating": 7,
            "cgpa": 7.6, "days_to_drive": 45, "weakest_topic": "Dynamic Programming",
            "projects_on_resume": 2, "battery_of_mock_interviews_done": 3,
        }.items():
            self.B.add(k, v)

        # ---- desires ----
        self.D.add(Desire(
            "SURVIVE_IMMINENT_DRIVE", 10.0,
            trigger=lambda b: b.get("days_to_drive") <= 7,
            satisfied=lambda b: b.get("days_to_drive") < 0,
            urgency=lambda b: 3.0 if b.get("days_to_drive") <= 3 else 2.0))
        self.D.add(Desire(
            "MASTER_WEAK_CODING_TOPIC", 8.0,
            trigger=lambda b: b.get("coding_score") < 70,
            satisfied=lambda b: b.get("coding_score") >= 70,
            urgency=lambda b: 1.0 + (70 - b.get("coding_score")) / 100))
        self.D.add(Desire(
            "CLEAR_APTITUDE_CUTOFF", 7.0,
            trigger=lambda b: b.get("aptitude_score") < 75,
            satisfied=lambda b: b.get("aptitude_score") >= 75))
        self.D.add(Desire(
            "ACHIEVE_INTERVIEW_READINESS", 6.5,
            trigger=lambda b: b.get("interview_rating") < 8,
            satisfied=lambda b: b.get("interview_rating") >= 8))
        self.D.add(Desire(
            "BUILD_PROJECT_PORTFOLIO", 4.0,
            trigger=lambda b: b.get("projects_on_resume") < 3,
            satisfied=lambda b: b.get("projects_on_resume") >= 3))

    # ---------------- the classic BDI control loop --------------------
    def deliberate_and_reconsider(self):
        """Reconsider intentions against the CURRENT belief state."""
        active = self.D.deliberate(self.B)
        if not active:
            return None
        top = active[0]
        cur = self.I.current()

        if cur is None:
            plan, steps = PLAN_LIBRARY[top.name]
            self.I.commit(Intention(top.name, plan, list(steps)))
            return self.I.current()

        # --- DYNAMIC PLAN RECALCULATION ---
        if cur.desire != top.name:
            cur_desire = next(d for d in self.D.desires if d.name == cur.desire)
            if top.priority(self.B) > cur_desire.priority(self.B):
                log("RECALC", f"priority inversion detected: '{top.name}' "
                              f"({top.priority(self.B)}) > '{cur.desire}' "
                              f"({cur_desire.priority(self.B)})")
                self.I.drop_current("superseded by higher-priority desire")
                plan, steps = PLAN_LIBRARY[top.name]
                self.I.commit(Intention(top.name, plan, list(steps)))
        # --- intention no longer needed (its desire got satisfied) ---
        elif cur_desire_satisfied(self.D, cur.desire, self.B):
            self.I.drop_current("desire already satisfied")
        return self.I.current()

    def execute_step(self):
        cur = self.I.current()
        if cur is None:
            return False
        if cur.done():
            log("INTENTION", f"COMPLETE plan '{cur.plan_name}'")
            self.I.stack.pop()
            return True
        step = cur.next_step()
        log("EXECUTE", f"[{cur.plan_name} {cur.progress()}] {step}")
        return True


def cur_desire_satisfied(D, name, B):
    d = next((x for x in D.desires if x.name == name), None)
    return d.satisfied(B) if d else False


# ======================================================================
# 6. VERIFICATION RUN
# ======================================================================
def sep(t):
    print("\n" + "=" * 88); print(f" {t}"); print("=" * 88)


def main():
    sep("BDI GOAL-DRIVEN PLACEMENT PREPARATION AGENT (Assignment 4.1)")
    ag = BDIAgent()

    sep("PHASE 0 :: INITIAL BDI STATE")
    ag.B.dump(); ag.D.dump(ag.B); ag.I.dump()

    sep("PHASE 1 :: DELIBERATION -> INTENTION SELECTION")
    ag.deliberate_and_reconsider()
    ag.I.dump()

    sep("PHASE 2 :: NORMAL PLAN EXECUTION (3 steps)")
    for _ in range(3):
        ag.execute_step()

    # ================= THE INTENTION SHIFT EVENT =====================
    sep("PHASE 3 :: UNEXPECTED ENVIRONMENTAL BELIEF UPDATE (mid-execution)")
    print("  >> External percept arrives: Amazon has moved its campus drive forward.\n")
    ag.B.update("days_to_drive", 3, reason="placement-cell notification")
    ag.B.update("company_announced", "Amazon", reason="placement-cell notification")

    sep("PHASE 4 :: DYNAMIC PLAN RECALCULATION TRIGGERED BY BELIEF CHANGE")
    ag.deliberate_and_reconsider()
    ag.D.dump(ag.B)
    ag.I.dump()

    sep("PHASE 5 :: EXECUTING THE NEW (SHIFTED) INTENTION")
    for _ in range(6):
        ag.execute_step()

    sep("PHASE 6 :: BELIEF UPDATE -> DESIRE SATISFACTION -> INTENTION RETIREMENT")
    ag.B.update("days_to_drive", -1, reason="drive completed")
    ag.B.update("coding_score", 78, reason="post-drive assessment")
    ag.deliberate_and_reconsider()
    ag.I.dump()

    sep("VERIFICATION SUMMARY")
    print(f"   Belief revisions performed  : {ag.B.revision_count}")
    print(f"   Intentions abandoned        : {len(ag.I.abandoned)}")
    for i in ag.I.abandoned:
        print(f"      - '{i.plan_name}' dropped at {i.progress()} (desire '{i.desire}')")
    print(f"   Active intention now        : "
          f"{ag.I.current().plan_name if ag.I.current() else 'none'}")
    print("\n   >> INTENTION SHIFT DEMONSTRATED: a belief change (days_to_drive 45 -> 3)")
    print("      caused the agent to abandon PLAN_CodingRemediation mid-execution and")
    print("      re-commit to PLAN_EmergencyCram WITHOUT any human instruction.")
    print("=" * 88)


if __name__ == "__main__":
    main()
