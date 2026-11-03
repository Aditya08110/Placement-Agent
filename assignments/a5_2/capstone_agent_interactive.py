"""
Assignment 5.2 : CAPSTONE -- Consolidated Autonomous Placement Preparation Agent
================================================================================
Integrates every module built across Units 1-5:

  UNIT 1  -> Condition-Action reflex layer + PEAS sensors        [ReflexLayer]
  UNIT 2  -> Daemon worker threads + socket messaging            [MonitorDaemons/AgentBus]
  UNIT 3  -> Contract-Net negotiation + utility optimizer        [NegotiationModule/Optimizer]
  UNIT 4  -> BDI cognition + ontological KB + live API           [BDICore/KnowledgeGraph]
  UNIT 5  -> HMAC signature gateway                              [SecurityGateway]

  UI      -> Live CLI dashboard

Run:  python capstone_agent.py            (full autonomous lifecycle)
      python capstone_agent.py --cycles 6
"""

import argparse
import hashlib
import hmac
import json
import queue
import random
import secrets
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List

# ==============================================================================
# GLOBAL BUS / SHUTDOWN
# ==============================================================================
EVENT_BUS = queue.Queue()
SHUTDOWN = threading.Event()
STATE_LOCK = threading.Lock()
RNG = random.Random(2026)

C_RESET, C_DIM, C_OK, C_WARN, C_ERR, C_HL = (
    "\033[0m", "\033[2m", "\033[92m", "\033[93m", "\033[91m", "\033[96m")


def now():
    return datetime.now().strftime("%H:%M:%S")


def log(unit, tag, msg, color=""):
    print(f"{C_DIM}[{now()}]{C_RESET} {C_HL}[U{unit}]{C_RESET} [{tag:<11}] {color}{msg}{C_RESET}")


# ==============================================================================
# UNIT 5 :: SECURITY GATEWAY
# ==============================================================================
TRUSTED = {
    "placement-cell": {"secret": b"CAPSTONE_KEY_CELL_2026", "role": "ADMIN"},
    "mentor-node":    {"secret": b"CAPSTONE_KEY_MENTOR_26", "role": "TRAINER"},
    "sensor-daemon":  {"secret": b"CAPSTONE_KEY_SENSOR_26", "role": "SENSOR"},
}
PERMS = {"ADMIN": {"PUSH_DRIVE", "UPDATE_PLAN", "PERCEPT"},
         "TRAINER": {"UPDATE_PLAN", "PERCEPT"},
         "SENSOR": {"PERCEPT"}}


def canon(d):
    return json.dumps(d, sort_keys=True, separators=(",", ":")).encode()


def sign(host, command, args, secret=None):
    secret = secret or TRUSTED.get(host, {}).get("secret", b"")
    body = {"host_id": host, "command": command, "args": args,
            "nonce": secrets.token_hex(6), "ts": int(time.time())}
    return {"body": body, "sig": hmac.new(secret, canon(body), hashlib.sha256).hexdigest()}


class SecurityGateway:
    def __init__(self):
        self.nonces, self.ok, self.blocked = set(), 0, 0
        self.blocked_events = []

    def verify(self, m):
        b, s = m.get("body", {}), m.get("sig", "")
        if not all(k in b for k in ("host_id", "command", "args", "nonce", "ts")):
            return self._no("malformed payload")
        h = TRUSTED.get(b["host_id"])
        if not h:
            return self._no(f"untrusted host '{b['host_id']}'")
        exp = hmac.new(h["secret"], canon(b), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(exp, s):
            return self._no(f"signature mismatch from '{b['host_id']}'")
        if b["nonce"] in self.nonces:
            return self._no("replay attack (nonce reuse)")
        if abs(int(time.time()) - b["ts"]) > 60:
            return self._no("stale message")
        if b["command"] not in PERMS[h["role"]]:
            return self._no(f"privilege escalation: {h['role']} -> {b['command']}")
        self.nonces.add(b["nonce"])
        self.ok += 1
        return b

    def _no(self, reason):
        self.blocked += 1
        self.blocked_events.append(reason)
        log(5, "SECURITY", f"BLOCKED: {reason}", C_ERR)
        return None


# ==============================================================================
# UNIT 4 :: KNOWLEDGE GRAPH
# ==============================================================================
KB = {
    "skills": {
        "arrays": {"w": 0.9, "pre": []}, "strings": {"w": 0.7, "pre": []},
        "recursion": {"w": 0.8, "pre": ["arrays"]},
        "dp": {"w": 1.0, "pre": ["recursion"]}, "graphs": {"w": 0.95, "pre": ["recursion"]},
        "trees": {"w": 0.85, "pre": ["recursion"]}, "oops": {"w": 0.75, "pre": []},
        "dbms": {"w": 0.8, "pre": []}, "os": {"w": 0.7, "pre": []},
        "aptitude": {"w": 0.85, "pre": []},
    },
    "companies": {
        "Amazon":     {"tier": 1, "cgpa": 8.0, "req": ["dp", "graphs", "trees"], "lpa": 44},
        "Freshworks": {"tier": 2, "cgpa": 7.5, "req": ["arrays", "dbms", "trees"], "lpa": 22},
        "Zoho":       {"tier": 2, "cgpa": 7.0, "req": ["arrays", "oops", "dp"], "lpa": 18},
        "Infosys":    {"tier": 3, "cgpa": 6.5, "req": ["aptitude", "oops"], "lpa": 6.5},
    },
    "resources": {"striver": ["arrays", "dp", "graphs", "trees"],
                  "neetcode": ["dp", "graphs"], "gfg": ["dbms", "os", "oops"],
                  "indiabix": ["aptitude"]},
}


class KnowledgeGraph:
    def closure(self, s, seen=None):
        seen = seen if seen is not None else set()
        for p in KB["skills"].get(s, {}).get("pre", []):
            if p not in seen:
                seen.add(p); self.closure(p, seen)
        return seen

    def gaps(self, levels, company):
        return [(s, levels.get(s, 0)) for s in KB["companies"][company]["req"]
                if levels.get(s, 0) < 70]

    def eligible(self, cgpa, levels):
        out = []
        for n, c in KB["companies"].items():
            if cgpa >= c["cgpa"]:
                cov = sum(1 for s in c["req"] if levels.get(s, 0) >= 70) / len(c["req"])
                out.append((n, c["tier"], round(cov, 2), c["lpa"]))
        return sorted(out, key=lambda x: (x[1], -x[2]))

    def resources(self, skill):
        return [r for r, t in KB["resources"].items() if skill in t]


# ==============================================================================
# UNIT 4 :: BDI CORE
# ==============================================================================
class DStatus(Enum):
    INACTIVE = "INACTIVE"; ACTIVE = "ACTIVE"; ACHIEVED = "ACHIEVED"


class BeliefBase:
    def __init__(self):
        self.b, self.revisions = {}, 0

    def set(self, k, v):
        self.b[k] = v

    def get(self, k, d=None):
        return self.b.get(k, d)

    def revise(self, k, v, src="percept"):
        old = self.b.get(k)
        if old == v:
            return False
        self.b[k] = v
        self.revisions += 1
        log(4, "BELIEF", f"rev#{self.revisions} {k}: {old} -> {v} ({src})", C_WARN)
        return True


@dataclass
class Desire:
    name: str; base: float
    trig: Callable; sat: Callable
    urg: Callable = lambda b: 1.0
    status: DStatus = DStatus.INACTIVE
    def prio(self, b): return round(self.base * self.urg(b), 2)


@dataclass
class Intention:
    desire: str; plan: str; steps: List[str]; cur: int = 0
    trace: List[str] = field(default_factory=list)
    def done(self): return self.cur >= len(self.steps)
    def step(self):
        s = self.steps[self.cur]; self.cur += 1; self.trace.append(s); return s
    def prog(self): return f"{self.cur}/{len(self.steps)}"


PLANS = {
    "SURVIVE_DRIVE": ("PLAN_EmergencyCram", [
        "freeze long-horizon goals", "load company question bank",
        "revise top-50 problems", "rehearse self-introduction", "confirm registration"]),
    "FIX_WEAK_SKILL": ("PLAN_SkillRemediation", [
        "query KB for weakest skill", "resolve prerequisite closure",
        "fetch curated resources", "solve graded problem ladder", "re-assess and revise belief"]),
    "PASS_APTITUDE": ("PLAN_AptitudeDrill", [
        "identify weak section", "run 30-question timed drill",
        "review errors", "re-test and revise belief"]),
    "INTERVIEW_READY": ("PLAN_InterviewPrep", [
        "generate question bank", "negotiate mentor slot (CNP)",
        "conduct mock interview", "ingest mentor feedback"]),
}


class BDICore:
    def __init__(self, kg):
        self.kg = kg
        self.B = BeliefBase()
        self.D: List[Desire] = []
        self.I: List[Intention] = []
        self.dropped: List[Intention] = []
        self._init()

    def _init(self):
        for k, v in {"cgpa": 7.6, "days_to_drive": 40, "aptitude": 62,
                     "interview_rating": 5, "target": "Freshworks",
                     "levels": {"arrays": 81, "strings": 76, "oops": 72, "recursion": 58,
                                "dp": 39, "graphs": 44, "trees": 63, "dbms": 68,
                                "os": 55, "aptitude": 62}}.items():
            self.B.set(k, v)

        self.D = [
            Desire("SURVIVE_DRIVE", 10.0,
                   lambda b: b.get("days_to_drive") <= 7,
                   lambda b: b.get("days_to_drive") < 0,
                   lambda b: 3.0 if b.get("days_to_drive") <= 3 else 2.0),
            Desire("FIX_WEAK_SKILL", 8.0,
                   lambda b: len(self.kg.gaps(b.get("levels"), b.get("target"))) > 0,
                   lambda b: len(self.kg.gaps(b.get("levels"), b.get("target"))) == 0),
            Desire("PASS_APTITUDE", 7.0,
                   lambda b: b.get("aptitude") < 75, lambda b: b.get("aptitude") >= 75),
            Desire("INTERVIEW_READY", 6.5,
                   lambda b: b.get("interview_rating") < 8,
                   lambda b: b.get("interview_rating") >= 8),
        ]

    def deliberate(self):
        active = []
        for d in self.D:
            if d.sat(self.B):
                if d.status != DStatus.ACHIEVED:
                    d.status = DStatus.ACHIEVED
                    log(4, "DESIRE", f"'{d.name}' ACHIEVED", C_OK)
                continue
            if d.trig(self.B):
                d.status = DStatus.ACTIVE
                active.append(d)
            else:
                d.status = DStatus.INACTIVE
        active.sort(key=lambda d: -d.prio(self.B))
        if not active:
            return None
        top = active[0]
        cur = self.I[-1] if self.I else None
        if cur is None:
            p, s = PLANS[top.desire if hasattr(top, 'desire') else top.name]
            self.I.append(Intention(top.name, p, list(s)))
            log(4, "INTENTION", f"COMMIT {p} (desire {top.name}, prio {top.prio(self.B)})")
        elif cur.desire != top.name:
            cd = next(d for d in self.D if d.name == cur.desire)
            if top.prio(self.B) > cd.prio(self.B):
                log(4, "RECALC", f"priority inversion {top.name}({top.prio(self.B)}) > "
                                 f"{cur.desire}({cd.prio(self.B)})", C_WARN)
                self.dropped.append(self.I.pop())
                log(4, "INTENTION", f"DROP {cur.plan} at {cur.prog()}", C_WARN)
                p, s = PLANS[top.name]
                self.I.append(Intention(top.name, p, list(s)))
                log(4, "INTENTION", f"COMMIT {p} (re-planned)", C_OK)
        return self.I[-1] if self.I else None

    def execute(self):
        if not self.I:
            return None
        cur = self.I[-1]
        if cur.done():
            log(4, "INTENTION", f"COMPLETE {cur.plan}", C_OK)
            self.I.pop()
            return "COMPLETE"
        s = cur.step()
        log(4, "EXECUTE", f"[{cur.plan} {cur.prog()}] {s}")
        return s


# ==============================================================================
# UNIT 3 :: UTILITY OPTIMIZER + CONTRACT NET NEGOTIATION
# ==============================================================================
RESOURCE_OPTIONS = [
    ("DSA Bootcamp",      8500, 60, 82, 74, 8.6),
    ("Aptitude Crash",    3200, 25, 45, 38, 7.4),
    ("Mock Bundle",       6800, 20, 40, 78, 9.1),
    ("Core CS Kit",       4100, 35, 58, 51, 7.9),
    ("Product Sprint",    9900, 55, 79, 85, 8.8),
    ("Free Track",           0, 80, 35, 22, 5.2),
    ("Resume Lab",        2400, 10, 18, 44, 8.0),
    ("FAANG Track",      14500, 90, 95, 92, 9.4),
    ("Fullstack Pack",   11200, 110, 88, 69, 8.2),
    ("1-on-1 Mentor",    19800, 45, 90, 88, 9.7),
]


class UtilityOptimizer:
    W = (0.25, 0.30, 0.15, 0.20, 0.10)

    def __init__(self, budget=12000, hours=70, min_rating=7.0):
        self.budget, self.hours, self.min_rating = budget, hours, min_rating

    def utility(self, o):
        _, cost, hrs, sg, pb, rt = o
        mx = max(x[3] for x in RESOURCE_OPTIONS)
        b = self.budget or 1; h = self.hours or 1
        w1, w2, w3, w4, w5 = self.W
        return round(w1*(sg/mx) + w2*(pb/100) + w3*(rt/10)
                     + w4*max(0, 1-cost/b) + w5*max(0, 1-hrs/h), 4)

    def optimize(self):
        feas = [o for o in RESOURCE_OPTIONS
                if o[1] <= self.budget and o[2] <= self.hours and o[5] >= self.min_rating]
        if not feas:
            log(3, "OPTIMIZER", "NO_VIABLE_PLAN (all options infeasible)", C_ERR)
            return None, []
        scored = sorted(((self.utility(o), o) for o in feas), key=lambda x: -x[0])
        return scored[0], scored


class Mentor:
    def __init__(self, name, quality, minfee, slots, flex, seed):
        self.name, self.quality, self.minfee = name, quality, minfee
        self.slots, self.flex, self.active = slots, flex, True
        self.fee = minfee * random.Random(seed).uniform(1.4, 1.7)

    def counter(self, target):
        if not self.active:
            return None
        nf = self.fee - (self.fee - target) * self.flex
        if nf < self.minfee:
            if self.fee <= self.minfee * 1.02:
                self.active = False
                return None
            nf = self.minfee
        self.fee = nf
        return {"agent": self.name, "fee": round(nf, 2),
                "slots": self.slots, "quality": self.quality}


class NegotiationModule:
    def __init__(self, budget=9000, needed=6):
        self.budget, self.needed = budget, needed

    def buyer_utility(self, b):
        if b["fee"] > self.budget:
            return -1
        return round(0.45*(1-b["fee"]/self.budget) + 0.35*(b["quality"]/10)
                     + 0.20*min(b["slots"]/self.needed, 1), 4)

    def run(self):
        mentors = [Mentor("Mentor-A", 9, 4200, 5, 0.30, 1),
                   Mentor("Mentor-B", 7, 3100, 8, 0.45, 2),
                   Mentor("Mentor-C", 8, 3700, 7, 0.25, 3)]
        log(3, "CNP", f"CFP broadcast: {self.needed} mock slots under Rs.{self.budget:,}")
        target, thresh, winner = self.budget*0.55, 0.70, None
        for rnd in range(1, 6):
            bids = [m.counter(target) for m in mentors if m.active]
            bids = [b for b in bids if b]
            if not bids:
                break
            scored = sorted(((self.buyer_utility(b), b) for b in bids
                             if self.buyer_utility(b) >= 0), key=lambda x: -x[0])
            for u, b in scored:
                log(3, "CNP", f"  R{rnd} {b['agent']}: Rs.{b['fee']:,.0f} "
                              f"{b['slots']}sl q{b['quality']} -> U={u}")
            if scored and scored[0][0] >= thresh:
                winner = scored[0]
                log(3, "CNP", f"ACCEPT {winner[1]['agent']} U={winner[0]} >= {thresh:.2f}", C_OK)
                break
            target *= 1.06; thresh -= 0.035
        if winner:
            log(3, "CNP", f"HANDSHAKE COMPLETE -> contract awarded to "
                          f"{winner[1]['agent']} @ Rs.{winner[1]['fee']:,.0f}", C_OK)
        return winner


# ==============================================================================
# UNIT 1 :: REFLEX LAYER
# ==============================================================================
class ReflexLayer:
    RULES = [
        ("R1_URGENT",   lambda s: s["days"] <= 7,
         lambda s: f"switch to RAPID-REVISION ({s['days']}d left)"),
        ("R2_CODING",   lambda s: s["weakest_lvl"] < 50,
         lambda s: f"assign graded ladder on '{s['weakest']}' ({s['weakest_lvl']}%)"),
        ("R3_APTITUDE", lambda s: s["apt"] < 50,
         lambda s: f"push 30-question aptitude drill ({s['apt']}%)"),
        ("R4_MOCK",     lambda s: s["mock"] <= 4,
         lambda s: f"schedule mock interview (rating {s['mock']}/10)"),
        ("R5_IDLE",     lambda s: s["hours"] < 1.0,
         lambda s: f"send reminder ({s['hours']}h studied today)"),
    ]

    def react(self, s):
        fired = []
        for n, c, a in self.RULES:
            if c(s):
                fired.append((n, a(s)))
                log(1, "REFLEX", f"{n} -> {a(s)}")
        return fired


# ==============================================================================
# UNIT 2 :: DAEMON WORKERS  (signed percepts onto the bus)
# ==============================================================================
def coding_daemon(interval=1.1):
    r = random.Random(101)
    while not SHUTDOWN.is_set():
        EVENT_BUS.put(sign("sensor-daemon", "PERCEPT",
                           {"type": "CODING", "skill": r.choice(list(KB["skills"])),
                            "delta": r.randint(-3, 9)}))
        SHUTDOWN.wait(interval)


def aptitude_daemon(interval=1.7):
    r = random.Random(202)
    while not SHUTDOWN.is_set():
        EVENT_BUS.put(sign("sensor-daemon", "PERCEPT",
                           {"type": "APTITUDE", "score": r.randint(45, 96)}))
        SHUTDOWN.wait(interval)


def drive_daemon(interval=2.9):
    r = random.Random(303)
    while not SHUTDOWN.is_set():
        if r.random() < 0.5:
            EVENT_BUS.put(sign("placement-cell", "PUSH_DRIVE",
                               {"company": r.choice(list(KB["companies"])),
                                "days": r.choice([3, 5, 12, 25])}))
        SHUTDOWN.wait(interval)


# ------------------------------------------------------------------
# INTERACTIVE CONSOLE SENSOR  (Unit 1 sensor + Unit 2 worker thread)
# ------------------------------------------------------------------
# This is a SENSOR, not a command prompt. Anything typed here is
# converted into a signed percept and published onto the SAME event
# bus the automated daemons use. The agent does not wait for it, does
# not block on it, and applies the identical Unit-5 security gates.
# The agent stays autonomous; the operator merely gains the ability to
# inject an environmental event on demand.
# ------------------------------------------------------------------
HELP_TEXT = """
  drive <Company> <days>   announce a placement drive  (e.g. drive Amazon 3)
  score <skill> <0-100>    report a new skill score    (e.g. score dp 85)
  apt <0-100>              report an aptitude result   (e.g. apt 91)
  mock <1-10>              report a mock-interview rating
  target <Company>         change the target company
  attack                   inject a forged message from an untrusted host
  help                     show this list
  quit                     stop the agent
"""


def console_sensor_daemon():
    """Reads operator keystrokes and publishes them as signed percepts."""
    while not SHUTDOWN.is_set():
        try:
            raw = input()
        except (EOFError, KeyboardInterrupt):
            SHUTDOWN.set()
            return
        line = raw.strip()
        if not line:
            continue
        parts = line.split()
        cmd = parts[0].lower()

        try:
            if cmd in ("quit", "exit", "q"):
                log(1, "SENSOR-IN", "operator requested shutdown", C_WARN)
                SHUTDOWN.set()
                return

            elif cmd == "help":
                print(HELP_TEXT)

            elif cmd == "drive" and len(parts) >= 3:
                company, days = parts[1], int(parts[2])
                EVENT_BUS.put(sign("placement-cell", "PUSH_DRIVE",
                                   {"company": company, "days": days}))
                log(1, "SENSOR-IN", f"percept injected: drive '{company}' in {days}d", C_HL)

            elif cmd == "score" and len(parts) >= 3:
                skill, val = parts[1].lower(), int(parts[2])
                if skill not in KB["skills"]:
                    log(1, "SENSOR-IN", f"unknown skill '{skill}'. known: "
                                        f"{', '.join(KB['skills'])}", C_ERR)
                    continue
                EVENT_BUS.put(sign("sensor-daemon", "PERCEPT",
                                   {"type": "SET_SKILL", "skill": skill, "value": val}))
                log(1, "SENSOR-IN", f"percept injected: {skill} = {val}%", C_HL)

            elif cmd == "apt" and len(parts) >= 2:
                EVENT_BUS.put(sign("sensor-daemon", "PERCEPT",
                                   {"type": "APTITUDE", "score": int(parts[1])}))
                log(1, "SENSOR-IN", f"percept injected: aptitude = {parts[1]}%", C_HL)

            elif cmd == "mock" and len(parts) >= 2:
                EVENT_BUS.put(sign("mentor-node", "UPDATE_PLAN",
                                   {"type": "MOCK", "rating": int(parts[1])}))
                log(1, "SENSOR-IN", f"percept injected: mock rating = {parts[1]}/10", C_HL)

            elif cmd == "target" and len(parts) >= 2:
                company = parts[1]
                if company not in KB["companies"]:
                    log(1, "SENSOR-IN", f"unknown company. known: "
                                        f"{', '.join(KB['companies'])}", C_ERR)
                    continue
                EVENT_BUS.put(sign("placement-cell", "UPDATE_PLAN",
                                   {"type": "TARGET", "company": company}))
                log(1, "SENSOR-IN", f"percept injected: target = {company}", C_HL)

            elif cmd == "attack":
                EVENT_BUS.put(sign("placement-cell", "PUSH_DRIVE",
                                   {"company": "FakeCorp", "days": 0},
                                   secret=b"ATTACKER_GUESSED_KEY"))
                log(1, "SENSOR-IN", "forged message injected -- watch the U5 gate", C_ERR)

            else:
                log(1, "SENSOR-IN", f"unrecognised input '{line}'. type 'help'", C_ERR)

        except ValueError:
            log(1, "SENSOR-IN", f"bad number in '{line}'. type 'help'", C_ERR)


def intruder_daemon(interval=2.3):
    """Simulates continuous hostile traffic against the agent."""
    r = random.Random(404)
    attacks = [
        lambda: sign("evil-host", "PUSH_DRIVE", {"company": "Fake"}, b"badkey"),
        lambda: sign("placement-cell", "PUSH_DRIVE", {"c": "X"}, b"WRONG_GUESSED_KEY"),
        lambda: sign("sensor-daemon", "PUSH_DRIVE", {"company": "Escalate"}),
        lambda: {"body": {"command": "PERCEPT"}, "sig": ""},
    ]
    while not SHUTDOWN.is_set():
        EVENT_BUS.put(r.choice(attacks)())
        SHUTDOWN.wait(interval)


# ==============================================================================
# THE INTEGRATED CAPSTONE AGENT
# ==============================================================================
class PlacementPreparationAgent:
    def __init__(self):
        self.kg = KnowledgeGraph()
        self.bdi = BDICore(self.kg)
        self.sec = SecurityGateway()
        self.reflex = ReflexLayer()
        self.opt = UtilityOptimizer()
        self.neg = NegotiationModule()
        self.percepts = 0
        self.reflex_fires = 0
        self.cycle = 0
        self.contract = None
        self.selected_resource = None

    # ---------------- SENSE (Unit 1 + 2 + 5) --------------------------
    def sense(self):
        drained = []
        while True:
            try:
                drained.append(EVENT_BUS.get_nowait())
            except queue.Empty:
                break
        for m in drained:
            body = self.sec.verify(m)      # UNIT 5 gate
            if not body:
                continue
            self.percepts += 1
            a = body["args"]
            with STATE_LOCK:
                if body["command"] == "PERCEPT" and a["type"] == "CODING":
                    lv = dict(self.bdi.B.get("levels"))
                    lv[a["skill"]] = max(0, min(100, lv.get(a["skill"], 50) + a["delta"]))
                    self.bdi.B.revise("levels", lv, f"coding-daemon/{a['skill']}")
                elif body["command"] == "PERCEPT" and a["type"] == "APTITUDE":
                    self.bdi.B.revise("aptitude", a["score"], "aptitude-daemon")
                    lv = dict(self.bdi.B.get("levels")); lv["aptitude"] = a["score"]
                    self.bdi.B.set("levels", lv)
                elif body["command"] == "PERCEPT" and a["type"] == "SET_SKILL":
                    lv = dict(self.bdi.B.get("levels"))
                    lv[a["skill"]] = max(0, min(100, a["value"]))
                    self.bdi.B.revise("levels", lv, f"operator/{a['skill']}")
                elif body["command"] == "UPDATE_PLAN" and a.get("type") == "MOCK":
                    self.bdi.B.revise("interview_rating", a["rating"], "operator/mock")
                elif body["command"] == "UPDATE_PLAN" and a.get("type") == "TARGET":
                    self.bdi.B.revise("target", a["company"], "operator/target")
                elif body["command"] == "PUSH_DRIVE":
                    self.bdi.B.revise("days_to_drive", a["days"],
                                      f"placement-cell/{a['company']}")
                    self.bdi.B.revise("announced_company", a["company"], "placement-cell")
        return len(drained)

    # ---------------- REFLEX (Unit 1) ---------------------------------
    def reflex_pass(self):
        lv = self.bdi.B.get("levels")
        weakest = min(lv, key=lv.get)
        s = {"days": self.bdi.B.get("days_to_drive"), "apt": self.bdi.B.get("aptitude"),
             "mock": self.bdi.B.get("interview_rating"), "hours": round(RNG.uniform(0, 5), 1),
             "weakest": weakest, "weakest_lvl": lv[weakest]}
        f = self.reflex.react(s)
        self.reflex_fires += len(f)
        return f

    # ---------------- DASHBOARD (UI layer) ----------------------------
    def dashboard(self):
        B = self.bdi.B
        lv = B.get("levels")
        print("\n" + "+" + "-" * 86 + "+")
        print(f"| {'PLACEMENT PREPARATION AGENT :: LIVE DASHBOARD':<60}"
              f"cycle {self.cycle:>3}  {now()}  |")
        print("+" + "-" * 86 + "+")
        print(f"| CGPA {B.get('cgpa')}   Target: {B.get('target'):<12} "
              f"Drive in: {B.get('days_to_drive')}d   "
              f"Aptitude: {B.get('aptitude')}%   Mock: {B.get('interview_rating')}/10"
              f"{'':>4}|")
        print("+" + "-" * 86 + "+")
        bar = ""
        for k, v in sorted(lv.items(), key=lambda x: x[1]):
            filled = int(v / 10)
            col = C_ERR if v < 50 else (C_WARN if v < 70 else C_OK)
            bar += f"|  {k:<11}{col}{'#'*filled}{'.'*(10-filled)}{C_RESET} {v:>3}%{'':>56}|\n"
        print(bar, end="")
        print("+" + "-" * 86 + "+")
        act = [d.name for d in self.bdi.D if d.status == DStatus.ACTIVE]
        ach = [d.name for d in self.bdi.D if d.status == DStatus.ACHIEVED]
        cur = self.bdi.I[-1] if self.bdi.I else None
        print(f"| DESIRES active: {', '.join(act) or '-':<66}|")
        print(f"| DESIRES done  : {', '.join(ach) or '-':<66}|")
        print(f"| INTENTION     : {(cur.plan + ' ' + cur.prog()) if cur else 'idle':<66}|")
        print("+" + "-" * 86 + "+")
        print(f"| SECURITY  accepted={self.sec.ok:<4} blocked={self.sec.blocked:<4} "
              f"| PERCEPTS {self.percepts:<4} | REFLEX FIRES {self.reflex_fires:<4}"
              f"| BELIEF REVS {self.bdi.B.revisions:<4}|")
        print("+" + "-" * 86 + "+")

    # ---------------- FULL LIFECYCLE ----------------------------------
    def run(self, cycles=8, interactive=False):
        print("=" * 88)
        print(" CAPSTONE :: AUTONOMOUS PLACEMENT PREPARATION AGENT (Assignment 5.2)")
        print(" Modules: U1 Reflex | U2 Daemons+Bus | U3 CNP+Utility | U4 BDI+KB | U5 Crypto")
        if interactive:
            print(" MODE   : INTERACTIVE -- console is an extra SENSOR, not a command prompt.")
            print("          The agent keeps running whether or not you type anything.")
            print(HELP_TEXT)
        print("=" * 88)

        specs = [(coding_daemon, "CodingDaemon"), (aptitude_daemon, "AptitudeDaemon"),
                 (intruder_daemon, "IntruderDaemon")]
        if interactive:
            # The operator becomes the source of drive announcements, so the
            # automated DriveDaemon is stood down to keep cause and effect legible.
            specs.append((console_sensor_daemon, "ConsoleSensor"))
        else:
            specs.insert(2, (drive_daemon, "DriveDaemon"))
        workers = [threading.Thread(target=f, daemon=True, name=n) for f, n in specs]
        for w in workers:
            w.start()
            log(2, "DAEMON", f"started '{w.name}' (daemon={w.daemon})")

        # --- one-time strategic planning (Unit 3) ---
        print("\n" + "-" * 88)
        log(3, "OPTIMIZER", "running constrained utility maximization over 10 options")
        best, ranked = self.opt.optimize()
        if best:
            self.selected_resource = best
            for u, o in ranked[:4]:
                log(3, "OPTIMIZER", f"  {o[0]:<16} U={u}")
            log(3, "OPTIMIZER", f"OPTIMAL -> '{best[1][0]}' U={best[0]} "
                                f"(Rs.{best[1][1]:,}, {best[1][2]}h)", C_OK)
        print()
        self.contract = self.neg.run()

        # --- autonomous loop ---
        c = 0
        while True:
            c += 1
            if not interactive and c > cycles:
                break
            if interactive and SHUTDOWN.is_set():
                break
            self.cycle = c
            print("\n" + "=" * 88)
            print(f" AUTONOMOUS CYCLE {c}" + ("" if interactive else f"/{cycles}"))
            print("=" * 88)
            n = self.sense()                      # U1 sensors + U2 bus + U5 gate
            log(2, "BUS", f"drained {n} messages from event bus")
            self.reflex_pass()                    # U1
            self.bdi.deliberate()                 # U4
            for _ in range(2):
                self.bdi.execute()                # U4
            self.dashboard()                      # UI
            time.sleep(0.9)

        # --- shutdown ---
        print("\n" + "-" * 88)
        SHUTDOWN.set()
        for w in workers:
            w.join(timeout=2)
            log(2, "DAEMON", f"'{w.name}' joined (alive={w.is_alive()})")

        self.final_report()

    def final_report(self):
        B = self.bdi.B
        print("\n" + "=" * 88)
        print(" FINAL SYSTEM REPORT")
        print("=" * 88)
        print(f" UNIT 1  reflex rules fired          : {self.reflex_fires}")
        print(f" UNIT 2  authenticated percepts      : {self.percepts} (4 daemon threads)")
        if self.contract:
            u, b = self.contract
            print(f" UNIT 3  negotiated contract         : {b['agent']} @ Rs.{b['fee']:,.0f}, "
                  f"{b['slots']} slots, buyer-U={u}")
        if self.selected_resource:
            u, o = self.selected_resource
            print(f" UNIT 3  optimal resource selected   : {o[0]} (U={u})")
        print(f" UNIT 4  belief revisions            : {B.revisions}")
        print(f" UNIT 4  intentions dropped/replanned: {len(self.bdi.dropped)}")
        for i in self.bdi.dropped:
            print(f"            - {i.plan} dropped at {i.prog()}")
        print(f" UNIT 5  commands accepted / blocked : {self.sec.ok} / {self.sec.blocked}")
        for r in sorted(set(self.sec.blocked_events)):
            print(f"            - blocked: {r}")
        lv = B.get("levels")
        print(f"\n ELIGIBILITY (cgpa {B.get('cgpa')}):")
        for n, t, cov, lpa in self.kg.eligible(B.get("cgpa"), lv):
            print(f"    {n:<12} tier-{t}  skill-coverage {cov*100:>5.0f}%  {lpa} LPA")
        print(f"\n STATUS: agent completed {self.cycle} autonomous cycles with no human input.")
        print("=" * 88)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", type=int, default=8)
    ap.add_argument("--interactive", "-i", action="store_true",
                    help="enable the console sensor; runs until you type 'quit'")
    a = ap.parse_args()
    try:
        PlacementPreparationAgent().run(a.cycles, interactive=a.interactive)
    except KeyboardInterrupt:
        SHUTDOWN.set()
        print("\ninterrupted -- agent stopped.")
