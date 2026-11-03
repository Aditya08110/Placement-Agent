"""
Assignment 3.2 : Self-Interested Agent Utility Optimization
Project: Placement Preparation Agent
------------------------------------------------------------------
The agent must pick ONE training/course package out of 10 complex
options under hard constraints, maximizing an explicit mathematical
utility function. Includes brute-force + greedy heuristic + a
constrained knapsack variant, plus constraint-boundary resilience.

UTILITY MODEL
-------------
Normalise each attribute to [0,1]:
   n_skill  = skill_gain / max_skill_gain
   n_place  = placement_boost / 100
   n_rating = mentor_rating / 10
   n_cost   = 1 - (cost / budget)                (cheaper is better)
   n_time   = 1 - (hours / available_hours)      (faster is better)

   U(x) = w1*n_skill + w2*n_place + w3*n_rating + w4*n_cost + w5*n_time
          - PENALTY(x)
   where  sum(wi) = 1
   PENALTY(x) = 0.25 * (overlap_topics_already_mastered / total_topics)

HARD CONSTRAINTS (feasibility filter):
   cost  <= budget
   hours <= available_hours
   mentor_rating >= min_rating

Run:  python utility_optimizer.py
"""

from itertools import combinations

# ======================================================================
# 1. THE 10 COMPLEX OPTIONS  (search space)
# ======================================================================
OPTIONS = [
    # id, name,                     cost, hours, skill_gain, placement_boost, rating, topics
    (1,  "DSA Bootcamp Pro",        8500, 60, 82, 74, 8.6, {"Arrays","DP","Graphs","Trees"}),
    (2,  "Aptitude Crash Course",   3200, 25, 45, 38, 7.4, {"Quant","LR","Verbal"}),
    (3,  "FAANG Interview Track",  14500, 90, 95, 92, 9.4, {"DP","Graphs","System Design"}),
    (4,  "Core CS Revision Kit",    4100, 35, 58, 51, 7.9, {"OS","DBMS","CN","OOPS"}),
    (5,  "Mock Interview Bundle",   6800, 20, 40, 78, 9.1, {"Communication","HR"}),
    (6,  "Full Stack Placement",   11200, 110, 88, 69, 8.2, {"Web","DBMS","OOPS"}),
    (7,  "Free Community Track",       0, 80, 35, 22, 5.2, {"Arrays","Strings"}),
    (8,  "Resume + LinkedIn Lab",   2400, 10, 18, 44, 8.0, {"Resume","Branding"}),
    (9,  "Product Company Sprint", 9900, 55, 79, 85, 8.8, {"DP","System Design","OOPS"}),
    (10, "Premium 1-on-1 Mentor",  19800, 45, 90, 88, 9.7, {"DP","Graphs","HR","System Design"}),
]

# ======================================================================
# 2. AGENT PROFILE / CONSTRAINTS / PREFERENCE WEIGHTS
# ======================================================================
class SelfInterestedAgent:
    def __init__(self):
        self.budget = 12000            # Rs.
        self.available_hours = 70      # hours before placement season
        self.min_rating = 7.0
        self.mastered = {"Arrays", "Strings", "OOPS"}   # already strong -> penalty
        # w_skill, w_place, w_rating, w_cost, w_time  (must sum to 1.0)
        self.w = (0.25, 0.30, 0.15, 0.20, 0.10)
        assert abs(sum(self.w) - 1.0) < 1e-9, "weights must sum to 1"

    # ---------------- FEASIBILITY (hard constraints) ------------------
    def is_feasible(self, o):
        _id, name, cost, hours, sg, pb, rating, topics = o
        violations = []
        if cost > self.budget:
            violations.append(f"cost {cost}>{self.budget}")
        if hours > self.available_hours:
            violations.append(f"hours {hours}>{self.available_hours}")
        if rating < self.min_rating:
            violations.append(f"rating {rating}<{self.min_rating}")
        return (len(violations) == 0), violations

    # ---------------- UTILITY FUNCTION --------------------------------
    def utility(self, o, max_sg=None):
        _id, name, cost, hours, sg, pb, rating, topics = o
        max_sg = max_sg or max(x[4] for x in OPTIONS)
        w1, w2, w3, w4, w5 = self.w

        # ---- constraint boundary resilience: guard divide-by-zero ----
        budget = self.budget if self.budget > 0 else 1
        hrs_cap = self.available_hours if self.available_hours > 0 else 1

        n_skill = sg / max_sg
        n_place = pb / 100
        n_rating = rating / 10
        n_cost = max(0.0, 1 - cost / budget)
        n_time = max(0.0, 1 - hours / hrs_cap)

        overlap = len(topics & self.mastered)
        penalty = 0.25 * (overlap / max(len(topics), 1))

        u = (w1 * n_skill + w2 * n_place + w3 * n_rating
             + w4 * n_cost + w5 * n_time) - penalty
        return round(u, 4), {
            "n_skill": round(n_skill, 3), "n_place": round(n_place, 3),
            "n_rating": round(n_rating, 3), "n_cost": round(n_cost, 3),
            "n_time": round(n_time, 3), "penalty": round(penalty, 3),
        }

    # ---------------- OPTIMIZATION SEARCH -----------------------------
    def exhaustive_search(self):
        """Guaranteed-optimal brute force over the feasible set."""
        results, rejected = [], []
        max_sg = max(x[4] for x in OPTIONS)
        for o in OPTIONS:
            ok, why = self.is_feasible(o)
            if not ok:
                rejected.append((o, why))
                continue
            u, parts = self.utility(o, max_sg)
            results.append((u, o, parts))
        results.sort(key=lambda x: -x[0])
        return results, rejected

    def greedy_bundle(self, feasible):
        """Constrained multi-select: maximize total utility within budget+time."""
        best, best_u = None, -1
        pool = [(u, o) for u, o, _ in feasible]
        for r in (1, 2, 3):
            for combo in combinations(pool, r):
                cost = sum(o[2] for _, o in combo)
                hours = sum(o[3] for _, o in combo)
                if cost <= self.budget and hours <= self.available_hours:
                    total = sum(u for u, _ in combo)
                    if total > best_u:
                        best_u, best = total, combo
        return best, round(best_u, 4)


# ======================================================================
# 3. EXECUTION
# ======================================================================
def main():
    a = SelfInterestedAgent()
    print("=" * 96)
    print(" SELF-INTERESTED UTILITY OPTIMIZATION :: PLACEMENT PREP AGENT (Assignment 3.2)")
    print("=" * 96)
    print(f" CONSTRAINTS  budget<=Rs.{a.budget:,} | hours<={a.available_hours} | "
          f"mentor_rating>={a.min_rating}")
    print(f" WEIGHTS      skill={a.w[0]} place={a.w[1]} rating={a.w[2]} "
          f"cost={a.w[3]} time={a.w[4]}   (sum=1.0)")
    print(f" MASTERED     {sorted(a.mastered)}  -> redundancy penalty applies")

    print("\n" + "-" * 96)
    print(" SEARCH SPACE : 10 OPTIONS")
    print("-" * 96)
    print(f" {'ID':<3}{'Option':<26}{'Cost':>8}{'Hrs':>6}{'Skill':>7}{'Boost':>7}{'Rate':>6}")
    for o in OPTIONS:
        print(f" {o[0]:<3}{o[1]:<26}{o[2]:>8,}{o[3]:>6}{o[4]:>7}{o[5]:>7}{o[6]:>6}")

    feasible, rejected = a.exhaustive_search()

    print("\n" + "-" * 96)
    print(" STEP 1 :: CONSTRAINT FILTERING (infeasible options pruned)")
    print("-" * 96)
    for o, why in rejected:
        print(f"   [REJECT] id={o[0]} {o[1]:<26} violations: {', '.join(why)}")
    print(f"   -> {len(feasible)} feasible / {len(OPTIONS)} total")

    print("\n" + "-" * 96)
    print(" STEP 2 :: UTILITY EVALUATION OF FEASIBLE SET (ranked)")
    print("-" * 96)
    print(f" {'Rank':<6}{'ID':<4}{'Option':<26}{'U(x)':>8}   components")
    for i, (u, o, p) in enumerate(feasible, 1):
        comp = (f"skill={p['n_skill']} place={p['n_place']} rate={p['n_rating']} "
                f"cost={p['n_cost']} time={p['n_time']} pen={p['penalty']}")
        print(f" {i:<6}{o[0]:<4}{o[1]:<26}{u:>8.4f}   {comp}")

    best_u, best_o, best_p = feasible[0]
    print("\n" + "=" * 96)
    print(" STEP 3 :: OPTIMAL SINGLE DECISION (argmax U)")
    print("=" * 96)
    print(f"   SELECTED : [{best_o[0]}] {best_o[1]}")
    print(f"   U(x*)    = {best_u}")
    print(f"   Cost     = Rs.{best_o[2]:,} / Rs.{a.budget:,}   ({a.budget - best_o[2]:,} unused)")
    print(f"   Hours    = {best_o[3]} / {a.available_hours}")
    print(f"   PROOF    : U(x*) = {best_u} > U(runner-up '{feasible[1][1][1]}') = {feasible[1][0]}")
    print(f"              and U(x*) >= U(x) for ALL {len(feasible)} feasible x. OPTIMAL.")

    bundle, bu = a.greedy_bundle(feasible)
    print("\n" + "=" * 96)
    print(" STEP 4 :: CONSTRAINED MULTI-SELECT (knapsack extension)")
    print("=" * 96)
    tc = sum(o[2] for _, o in bundle); th = sum(o[3] for _, o in bundle)
    for u, o in bundle:
        print(f"   + [{o[0]}] {o[1]:<26} U={u:.4f}  Rs.{o[2]:,}  {o[3]}h")
    print(f"   TOTAL UTILITY = {bu} | cost Rs.{tc:,}/{a.budget:,} | hours {th}/{a.available_hours}")

    # ---------------- STEP 5 : BOUNDARY RESILIENCE --------------------
    print("\n" + "=" * 96)
    print(" STEP 5 :: ERROR / CONSTRAINT BOUNDARY RESILIENCE TESTS")
    print("=" * 96)
    tests = [
        ("Zero budget",        {"budget": 0}),
        ("Zero hours",         {"available_hours": 0}),
        ("Impossible rating",  {"min_rating": 10.0}),
        ("Negative budget",    {"budget": -5000}),
    ]
    for label, override in tests:
        t = SelfInterestedAgent()
        for k, v in override.items():
            setattr(t, k, v)
        try:
            f, r = t.exhaustive_search()
            if not f:
                print(f"   [{label:<18}] handled: 0 feasible options -> "
                      f"agent returns NO_VIABLE_PLAN (no crash)")
            else:
                print(f"   [{label:<18}] handled: {len(f)} feasible, "
                      f"best='{f[0][1][1]}' U={f[0][0]}")
        except ZeroDivisionError:
            print(f"   [{label:<18}] FAILED with ZeroDivisionError")
        except Exception as e:
            print(f"   [{label:<18}] FAILED: {type(e).__name__}: {e}")
    print("=" * 96)


if __name__ == "__main__":
    main()
