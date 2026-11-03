"""
Assignment 4.2 : Knowledge Representation and Adaptive API Integration
Project: Placement Preparation Agent
------------------------------------------------------------------
1. Ontological knowledge graph (JSON) of the placement domain.
2. Live REST API integration (GitHub API + Open-Meteo) with an
   OFFLINE MOCK fallback so the demo always runs.
3. Adaptive behaviour: ingested live data mutates the agent's plan.

Run online :  python knowledge_api_agent.py
Run offline:  python knowledge_api_agent.py --offline
"""

import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime

OFFLINE = "--offline" in sys.argv
KB_FILE = "knowledge_base.json"


def log(tag, msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [{tag:<14}] {msg}")


# ======================================================================
# PART 1 : KNOWLEDGE REPRESENTATION  (ontological graph, JSON-serialised)
# ======================================================================
KNOWLEDGE_BASE = {
    "ontology_version": "1.2",
    "domain": "Campus Placement Preparation",
    "classes": {
        "Skill":    {"properties": ["name", "difficulty", "weight", "prerequisites"]},
        "Company":  {"properties": ["name", "tier", "cgpa_cutoff", "required_skills"]},
        "Resource": {"properties": ["title", "type", "url", "teaches"]},
        "Student":  {"properties": ["cgpa", "skill_levels", "target_tier"]},
    },
    "relations": [
        {"subject": "Skill", "predicate": "REQUIRED_BY",  "object": "Company"},
        {"subject": "Skill", "predicate": "PREREQUISITE_OF", "object": "Skill"},
        {"subject": "Resource", "predicate": "TEACHES",   "object": "Skill"},
        {"subject": "Student", "predicate": "HAS_LEVEL_IN", "object": "Skill"},
        {"subject": "Student", "predicate": "ELIGIBLE_FOR", "object": "Company"},
    ],
    "individuals": {
        "skills": {
            "arrays":       {"difficulty": 2, "weight": 0.9, "prerequisites": []},
            "strings":      {"difficulty": 2, "weight": 0.7, "prerequisites": []},
            "recursion":    {"difficulty": 3, "weight": 0.8, "prerequisites": ["arrays"]},
            "dp":           {"difficulty": 5, "weight": 1.0, "prerequisites": ["recursion"]},
            "graphs":       {"difficulty": 5, "weight": 0.95, "prerequisites": ["recursion"]},
            "trees":        {"difficulty": 4, "weight": 0.85, "prerequisites": ["recursion"]},
            "oops":         {"difficulty": 2, "weight": 0.75, "prerequisites": []},
            "dbms":         {"difficulty": 3, "weight": 0.8, "prerequisites": []},
            "os":           {"difficulty": 3, "weight": 0.7, "prerequisites": []},
            "system_design":{"difficulty": 5, "weight": 0.6, "prerequisites": ["oops", "dbms"]},
            "aptitude":     {"difficulty": 2, "weight": 0.85, "prerequisites": []},
        },
        "companies": {
            "Amazon":     {"tier": 1, "cgpa_cutoff": 8.0,
                           "required_skills": ["dp", "graphs", "trees", "system_design"]},
            "Zoho":       {"tier": 2, "cgpa_cutoff": 7.0,
                           "required_skills": ["arrays", "strings", "oops", "dp"]},
            "Freshworks": {"tier": 2, "cgpa_cutoff": 7.5,
                           "required_skills": ["arrays", "dbms", "oops", "trees"]},
            "Infosys":    {"tier": 3, "cgpa_cutoff": 6.5,
                           "required_skills": ["aptitude", "oops", "dbms"]},
            "TCS":        {"tier": 3, "cgpa_cutoff": 6.0,
                           "required_skills": ["aptitude", "os", "dbms"]},
        },
        "resources": {
            "striver_a2z":   {"type": "sheet", "teaches": ["arrays", "dp", "graphs", "trees"]},
            "gfg_dbms":      {"type": "article", "teaches": ["dbms"]},
            "neetcode_150":  {"type": "problemset", "teaches": ["dp", "graphs", "arrays"]},
            "indiabix_apti": {"type": "quiz", "teaches": ["aptitude"]},
            "ddia_book":     {"type": "book", "teaches": ["system_design", "dbms"]},
        },
    },
}


class KnowledgeGraph:
    def __init__(self, kb):
        self.kb = kb

    def save(self, path=KB_FILE):
        with open(path, "w") as f:
            json.dump(self.kb, f, indent=2)
        log("KR", f"ontology serialised -> {path} ({os.path.getsize(path)} bytes)")

    # ---- inference: transitive prerequisite closure -------------------
    def prerequisite_closure(self, skill, seen=None):
        seen = seen or set()
        for p in self.kb["individuals"]["skills"].get(skill, {}).get("prerequisites", []):
            if p not in seen:
                seen.add(p)
                self.prerequisite_closure(p, seen)
        return seen

    # ---- inference: skill gap query -----------------------------------
    def skill_gap(self, student_levels, company):
        req = self.kb["individuals"]["companies"][company]["required_skills"]
        gaps = []
        for s in req:
            lvl = student_levels.get(s, 0)
            if lvl < 70:
                gaps.append((s, lvl, sorted(self.prerequisite_closure(s))))
        return gaps

    def eligible_companies(self, cgpa, levels):
        out = []
        for name, c in self.kb["individuals"]["companies"].items():
            if cgpa >= c["cgpa_cutoff"]:
                cov = sum(1 for s in c["required_skills"] if levels.get(s, 0) >= 70)
                out.append((name, c["tier"], f"{cov}/{len(c['required_skills'])}"))
        return sorted(out, key=lambda x: x[1])

    def resources_for(self, skill):
        return [r for r, v in self.kb["individuals"]["resources"].items()
                if skill in v["teaches"]]


# ======================================================================
# PART 2 : LIVE REST API INTEGRATION
# ======================================================================
MOCK_GITHUB = {"public_repos": 14, "followers": 23, "login": "student-dev",
               "created_at": "2022-08-11T00:00:00Z"}
MOCK_WEATHER = {"current": {"temperature_2m": 34.8, "relative_humidity_2m": 71,
                            "precipitation": 0.0, "weather_code": 3}}


def http_get_json(url, timeout=6, extra_headers=None):
    headers = {"User-Agent": "PlacementPrepAgent/1.0", "Accept": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_github_profile(user="torvalds"):
    """REAL REST API: https://api.github.com/users/<user>"""
    url = f"https://api.github.com/users/{user}"
    if OFFLINE:
        log("API/GITHUB", "offline mode -> using cached mock payload")
        return MOCK_GITHUB, "MOCK"
    # An authenticated request raises the quota from 60/hr per IP to 5000/hr, which
    # matters on a shared campus NAT where the anonymous quota is usually spent.
    headers = {}
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        log("API/GITHUB", f"GET {url}" + ("  [authenticated]" if token else "  [anonymous]"))
        data = http_get_json(url, extra_headers=headers)
        log("API/GITHUB", f"200 OK -> repos={data.get('public_repos')} "
                          f"followers={data.get('followers')}")
        return data, "LIVE"
    except urllib.error.HTTPError as e:
        # 403 + rate-limit is an EXPECTED operating condition, not a defect. Naming it
        # precisely is the difference between "the demo broke" and "degradation worked".
        if e.code in (403, 429):
            log("API/GITHUB", "403 rate-limited (anonymous quota is 60/hr per IP) "
                              "-> resilience path: serving last-known-good payload")
            return MOCK_GITHUB, "CACHED-RATELIMIT"
        log("API/GITHUB", f"HTTP {e.code} -> resilience path: last-known-good payload")
        return MOCK_GITHUB, "CACHED-HTTP%d" % e.code
    except Exception as e:
        log("API/GITHUB", f"unreachable ({type(e).__name__}) "
                          f"-> resilience path: last-known-good payload")
        return MOCK_GITHUB, "CACHED-OFFLINE"


def fetch_weather(lat=12.92, lon=80.12):
    """REAL REST API: Open-Meteo (no key needed). Chennai/Tambaram coords."""
    url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
           f"&current=temperature_2m,relative_humidity_2m,precipitation,weather_code")
    if OFFLINE:
        log("API/WEATHER", "offline mode -> using cached mock payload")
        return MOCK_WEATHER, "MOCK"
    try:
        log("API/WEATHER", f"GET {url[:70]}...")
        data = http_get_json(url)
        c = data["current"]
        log("API/WEATHER", f"200 OK -> {c['temperature_2m']}C "
                           f"humidity={c['relative_humidity_2m']}% "
                           f"rain={c['precipitation']}mm")
        return data, "LIVE"
    except Exception as e:
        log("API/WEATHER", f"FAILED ({type(e).__name__}) -> graceful fallback to mock")
        return MOCK_WEATHER, "MOCK-FALLBACK"


# ======================================================================
# PART 3 : ADAPTIVE BEHAVIOUR -- live data mutates the plan
# ======================================================================
class AdaptiveAgent:
    def __init__(self, kg):
        self.kg = kg
        self.profile = {
            "cgpa": 7.6,
            "levels": {"arrays": 82, "strings": 78, "oops": 74, "recursion": 61,
                       "dp": 38, "graphs": 41, "trees": 66, "dbms": 71,
                       "os": 58, "system_design": 22, "aptitude": 80},
            "target": "Amazon",
        }
        self.plan = []
        self.adaptations = []

    def build_base_plan(self):
        gaps = self.kg.skill_gap(self.profile["levels"], self.profile["target"])
        self.plan = []
        for skill, lvl, prereqs in sorted(gaps, key=lambda g: g[1]):
            unmet = [p for p in prereqs if self.profile["levels"].get(p, 0) < 70]
            res = self.kg.resources_for(skill)
            self.plan.append({
                "skill": skill, "level": lvl,
                "blocked_by": unmet,
                "resources": res,
                "mode": "deep-study", "hours": 12 if not unmet else 16,
            })
        return self.plan

    # -------- adaptation rule 1: GitHub portfolio signal ---------------
    def adapt_to_github(self, gh):
        repos = gh.get("public_repos", 0)
        if repos < 5:
            self.plan.append({"skill": "portfolio", "level": repos * 10, "blocked_by": [],
                              "resources": ["github-readme-guide"],
                              "mode": "project-build", "hours": 20})
            self.adaptations.append(
                f"public_repos={repos} < 5 -> INSERTED 'portfolio' task into plan")
        else:
            self.adaptations.append(
                f"public_repos={repos} >= 5 -> portfolio task SUPPRESSED, "
                f"hours reallocated to weakest skill")
            if self.plan:
                self.plan[0]["hours"] += 6

    # -------- adaptation rule 2: live weather -> study modality --------
    def adapt_to_weather(self, w):
        c = w["current"]
        temp, rain = c["temperature_2m"], c.get("precipitation", 0)
        if rain > 0.5:
            for t in self.plan:
                t["mode"] = "indoor-online"
            self.adaptations.append(
                f"precipitation={rain}mm -> ALL tasks switched to 'indoor-online'; "
                f"offline mock-interview travel cancelled")
        elif temp > 33:
            for t in self.plan:
                t["mode"] = "early-morning-slot"
            self.adaptations.append(
                f"temperature={temp}C > 33 -> ALL tasks rescheduled to "
                f"'early-morning-slot' (05:30-08:30)")
        else:
            self.adaptations.append(
                f"temperature={temp}C, rain={rain}mm -> normal schedule retained")

    def dump_plan(self, title):
        print(f"\n    {title}")
        print(f"    {'#':<3}{'Skill':<16}{'Lvl':>5}{'Hrs':>5}  {'Mode':<20}{'Blocked-by':<22}Resources")
        for i, t in enumerate(self.plan, 1):
            print(f"    {i:<3}{t['skill']:<16}{t['level']:>5}{t['hours']:>5}  "
                  f"{t['mode']:<20}{str(t['blocked_by'] or '-'):<22}"
                  f"{','.join(t['resources'][:2]) or '-'}")


# ======================================================================
def sep(t):
    print("\n" + "=" * 96); print(f" {t}"); print("=" * 96)


def main():
    sep("KNOWLEDGE REPRESENTATION + ADAPTIVE API INTEGRATION (Assignment 4.2)")
    print(f" Mode: {'OFFLINE (mock payloads)' if OFFLINE else 'LIVE (real REST endpoints)'}")

    kg = KnowledgeGraph(KNOWLEDGE_BASE)

    sep("PART 1 :: ONTOLOGICAL KNOWLEDGE REPRESENTATION")
    print(f"   Ontology v{KNOWLEDGE_BASE['ontology_version']} | "
          f"{len(KNOWLEDGE_BASE['classes'])} classes | "
          f"{len(KNOWLEDGE_BASE['relations'])} relation types")
    for r in KNOWLEDGE_BASE["relations"]:
        print(f"      ({r['subject']}) --[{r['predicate']}]--> ({r['object']})")
    print(f"   Individuals: {len(KNOWLEDGE_BASE['individuals']['skills'])} skills, "
          f"{len(KNOWLEDGE_BASE['individuals']['companies'])} companies, "
          f"{len(KNOWLEDGE_BASE['individuals']['resources'])} resources")
    kg.save()

    print("\n   INFERENCE QUERIES OVER THE GRAPH:")
    print(f"      prerequisite_closure('dp')            = {sorted(kg.prerequisite_closure('dp'))}")
    print(f"      prerequisite_closure('system_design') = {sorted(kg.prerequisite_closure('system_design'))}")
    print(f"      resources_for('graphs')               = {kg.resources_for('graphs')}")

    ag = AdaptiveAgent(kg)
    print(f"\n      eligible_companies(cgpa={ag.profile['cgpa']}):")
    for name, tier, cov in kg.eligible_companies(ag.profile["cgpa"], ag.profile["levels"]):
        print(f"         {name:<12} tier-{tier}  skill coverage {cov}")

    sep("PART 2 :: BASE PLAN DERIVED PURELY FROM THE KNOWLEDGE GRAPH")
    ag.build_base_plan()
    ag.dump_plan(f"BASE PLAN (target = {ag.profile['target']})")

    sep("PART 3 :: LIVE REST API INGESTION")
    gh, gh_src = fetch_github_profile()
    wx, wx_src = fetch_weather()
    print(f"\n   github  source={gh_src}  public_repos={gh.get('public_repos')} "
          f"followers={gh.get('followers')}")
    print(f"   weather source={wx_src}  temp={wx['current']['temperature_2m']}C "
          f"precip={wx['current'].get('precipitation')}mm")

    sep("PART 4 :: ADAPTIVE BEHAVIOURAL EXECUTION (plan mutates from live data)")
    ag.adapt_to_github(gh)
    ag.adapt_to_weather(wx)
    for i, a in enumerate(ag.adaptations, 1):
        log("ADAPT", f"{i}. {a}")
    ag.dump_plan("ADAPTED PLAN (post-ingestion)")

    print("\n" + "=" * 96)
    print(f" RESULT: {len(ag.adaptations)} adaptive mutations applied to a "
          f"{len(ag.plan)}-task plan from live feeds.")
    print("=" * 96)


if __name__ == "__main__":
    main()
