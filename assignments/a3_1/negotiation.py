"""
Assignment 3.1 : Multi-Agent Coordination Protocol (Contract Net Protocol)
Project: Placement Preparation Agent
------------------------------------------------------------------
SCENARIO: A StudentPrepAgent (Initiator/Manager) issues a Call-For-Proposals
for a mock-interview + training slot. Multiple MentorAgents (Participants)
bid. Multi-turn proposal / counter-proposal loop with utility-driven
stance modification, ending in a consensus handshake (CONTRACT AWARDED).

Run:  python negotiation.py
"""

import random
import time
from datetime import datetime

def log(who, act, msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {who:<16} --{act:<14}--> {msg}")

def banner(t):
    print("\n" + "=" * 88); print(f" {t}"); print("=" * 88)


# ======================================================================
# PARTICIPANT AGENT : Mentor / Trainer Agent (self-interested seller)
# ======================================================================
class MentorAgent:
    def __init__(self, name, quality, min_fee, max_slots, flexibility, seed):
        self.name = name
        self.quality = quality            # 0-10 training quality rating
        self.min_fee = min_fee            # reservation price (won't go below)
        self.fee = min_fee * random.Random(seed).uniform(1.45, 1.75)
        self.max_slots = max_slots
        self.slots = max_slots
        self.flexibility = flexibility    # concession rate per round
        self.rng = random.Random(seed)
        self.active = True

    def utility(self, fee, slots):
        """Seller utility: profit margin x slot efficiency."""
        margin = (fee - self.min_fee) / self.min_fee
        eff = slots / self.max_slots
        return round(margin * 0.7 + eff * 0.3, 4)

    def propose(self, rnd):
        if not self.active:
            return None
        return {"agent": self.name, "fee": round(self.fee, 2), "slots": self.slots,
                "quality": self.quality, "round": rnd,
                "utility": self.utility(self.fee, self.slots)}

    def counter(self, target_fee, rnd):
        """Modify stance: concede toward the manager's target, but never below cost."""
        gap = self.fee - target_fee
        new_fee = self.fee - gap * self.flexibility
        if new_fee < self.min_fee:
            if self.fee <= self.min_fee * 1.02:
                self.active = False
                log(self.name, "REFUSE", f"cannot go below reservation Rs.{self.min_fee}. WITHDRAWING.")
                return None
            new_fee = self.min_fee
        # occasionally add a slot as a sweetener
        if self.rng.random() < 0.4 and self.slots < self.max_slots + 2:
            self.slots += 1
        self.fee = new_fee
        log(self.name, "PROPOSE", f"round {rnd}: Rs.{self.fee:,.2f} | {self.slots} slots | "
                                  f"quality {self.quality}/10 | own-utility={self.utility(self.fee, self.slots)}")
        return self.propose(rnd)


# ======================================================================
# MANAGER AGENT : Student Prep Agent (buyer / CNP initiator)
# ======================================================================
class StudentPrepAgent:
    def __init__(self, budget, needed_slots, w_cost=0.45, w_qual=0.35, w_slot=0.20):
        self.name = "StudentPrepAgent"
        self.budget = budget
        self.needed = needed_slots
        self.w = (w_cost, w_qual, w_slot)
        self.target = budget * 0.55          # aggressive opening target
        self.accept_threshold = 0.72         # relaxes each round

    def utility(self, bid):
        """Buyer utility U = wc*(1-fee/budget) + wq*(quality/10) + ws*min(slots/needed,1)"""
        if bid["fee"] > self.budget:
            return -1.0
        wc, wq, ws = self.w
        u = (wc * (1 - bid["fee"] / self.budget)
             + wq * (bid["quality"] / 10)
             + ws * min(bid["slots"] / self.needed, 1.0))
        return round(u, 4)

    def evaluate(self, bids, rnd):
        scored = [(self.utility(b), b) for b in bids if b]
        scored = [(u, b) for u, b in scored if u >= 0]
        scored.sort(key=lambda x: -x[0])
        for u, b in scored:
            log(self.name, "EVALUATE", f"{b['agent']:<14} buyer-utility = {u}")
        return scored


def main():
    banner("MULTI-AGENT CONTRACT NET PROTOCOL :: MOCK-INTERVIEW TRAINING SLOT (Assignment 3.1)")

    manager = StudentPrepAgent(budget=12000, needed_slots=8)
    mentors = [
        MentorAgent("MentorAgent-A", quality=9, min_fee=5200, max_slots=6, flexibility=0.30, seed=1),
        MentorAgent("MentorAgent-B", quality=7, min_fee=3800, max_slots=10, flexibility=0.45, seed=2),
        MentorAgent("MentorAgent-C", quality=8, min_fee=4600, max_slots=8, flexibility=0.22, seed=3),
    ]

    log(manager.name, "INIT", f"budget=Rs.{manager.budget:,} | slots needed={manager.needed} | "
                              f"weights cost/quality/slots={manager.w}")
    for m in mentors:
        log(m.name, "REGISTER", f"reservation=Rs.{m.min_fee:,} quality={m.quality}/10 "
                                f"capacity={m.max_slots} flexibility={m.flexibility}")

    # ---------------- ROUND 0 : CALL FOR PROPOSALS --------------------
    banner("PHASE 1 :: CALL FOR PROPOSALS (CFP)")
    log(manager.name, "CFP", f"broadcast to {len(mentors)} participants: "
                             f"'need {manager.needed} mock-interview slots under Rs.{manager.budget:,}'")
    bids = [m.propose(0) for m in mentors]
    for b in bids:
        log(b["agent"], "PROPOSE", f"round 0: Rs.{b['fee']:,.2f} | {b['slots']} slots | quality {b['quality']}/10")
    manager.evaluate(bids, 0)

    # ---------------- MULTI-TURN NEGOTIATION --------------------------
    banner("PHASE 2 :: MULTI-TURN PROPOSAL / COUNTER-PROPOSAL LOOP")
    winner = None
    MAX_ROUNDS = 6
    for rnd in range(1, MAX_ROUNDS + 1):
        print(f"\n--- ROUND {rnd} " + "-" * 70)
        log(manager.name, "COUNTER", f"target price Rs.{manager.target:,.2f} | "
                                     f"acceptance threshold {manager.accept_threshold:.3f}")
        bids = [m.counter(manager.target, rnd) for m in mentors if m.active]
        bids = [b for b in bids if b]
        if not bids:
            log(manager.name, "FAIL", "all participants withdrew. Negotiation failed.")
            break

        scored = manager.evaluate(bids, rnd)
        if scored and scored[0][0] >= manager.accept_threshold:
            winner = scored[0]
            log(manager.name, "ACCEPT", f"utility {winner[0]} >= threshold "
                                        f"{manager.accept_threshold:.3f} -> intent to award")
            break

        # manager concedes: raise target, lower threshold
        manager.target = min(manager.target * 1.06, manager.budget * 0.92)
        manager.accept_threshold -= 0.035
        log(manager.name, "CONCEDE", f"no bid met threshold -> relaxing to "
                                     f"{manager.accept_threshold:.3f}")
        time.sleep(0.2)

    # ---------------- CONSENSUS HANDSHAKE -----------------------------
    banner("PHASE 3 :: CONSENSUS HANDSHAKE / CONTRACT AWARD")
    if winner:
        u, b = winner
        log(manager.name, "AWARD", f"CONTRACT -> {b['agent']}")
        log(b["agent"], "ACK", f"ACCEPT-PROPOSAL received. Committing {b['slots']} slots.")
        log(manager.name, "CONFIRM", "HANDSHAKE COMPLETE (3-way: CFP -> PROPOSE -> ACCEPT/ACK)")
        for m in mentors:
            if m.name != b["agent"]:
                log(manager.name, "REJECT", f"REJECT-PROPOSAL sent to {m.name}")
        print("\n  FINAL CONTRACT")
        print(f"    Provider        : {b['agent']}")
        print(f"    Agreed Fee      : Rs.{b['fee']:,.2f}  (budget Rs.{manager.budget:,})")
        print(f"    Slots Secured   : {b['slots']} / {manager.needed} required")
        print(f"    Trainer Quality : {b['quality']}/10")
        print(f"    Buyer  Utility  : {u}")
        print(f"    Seller Utility  : {b['utility']}")
        print(f"    Rounds Taken    : {b['round']}")
        print(f"    STATUS          : CONSENSUS REACHED -- NEGOTIATION TERMINATED")
    else:
        print("    STATUS : NO AGREEMENT within round limit.")
    print("=" * 88)


if __name__ == "__main__":
    main()
