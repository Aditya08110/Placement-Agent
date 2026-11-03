"""
Assignment 2.1 : Concurrent Task Daemonization using Threads and Workers
Project: Placement Preparation Agent
------------------------------------------------------------------
Background daemons poll the environment (coding platforms, placement
calendar, aptitude engine) WITHOUT blocking the agent's main event loop.
Thread safety via queue.Queue + threading.Lock.

Run:  python concurrent_agent.py
"""

import threading
import queue
import random
import time
from datetime import datetime

# ======================================================================
# SHARED STATE  (guarded by a lock)  +  SAFE MESSAGE QUEUE
# ======================================================================
percept_queue = queue.Queue()          # thread-safe producer -> consumer channel
state_lock = threading.Lock()          # guards shared_state
shutdown = threading.Event()

shared_state = {
    "coding_score": 55,
    "aptitude_score": 60,
    "open_drives": 0,
    "problems_solved": 0,
    "updates_applied": 0,
}

latency_log = []
latency_lock = threading.Lock()


def ts():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def log(worker, msg):
    print(f"[{ts()}] [{worker:<18}] {msg}")


# ======================================================================
# DAEMON WORKER 1 : polls coding platform (LeetCode/HackerRank) metrics
# ======================================================================
def coding_platform_monitor(interval=0.8):
    rng = random.Random(11)
    while not shutdown.is_set():
        t0 = time.perf_counter()
        solved = rng.randint(0, 3)
        score = rng.randint(40, 95)
        percept_queue.put({"src": "CODING", "solved": solved, "score": score})
        log("CodingMonitor", f"polled platform -> +{solved} solved, score={score}%")
        with latency_lock:
            latency_log.append(("CodingMonitor", (time.perf_counter() - t0) * 1000))
        shutdown.wait(interval)


# ======================================================================
# DAEMON WORKER 2 : polls campus placement drive calendar
# ======================================================================
def placement_calendar_monitor(interval=1.3):
    rng = random.Random(23)
    companies = ["TCS", "Infosys", "Zoho", "Amazon", "Wipro", "Freshworks"]
    while not shutdown.is_set():
        t0 = time.perf_counter()
        if rng.random() < 0.7:
            c = rng.choice(companies)
            percept_queue.put({"src": "DRIVE", "company": c,
                               "cutoff": rng.choice([6.5, 7.0, 7.5, 8.0])})
            log("DriveMonitor", f"new placement drive detected -> {c}")
        else:
            log("DriveMonitor", "no new drives this cycle")
        with latency_lock:
            latency_log.append(("DriveMonitor", (time.perf_counter() - t0) * 1000))
        shutdown.wait(interval)


# ======================================================================
# DAEMON WORKER 3 : aptitude test result poller
# ======================================================================
def aptitude_monitor(interval=1.0):
    rng = random.Random(37)
    while not shutdown.is_set():
        t0 = time.perf_counter()
        score = rng.randint(35, 99)
        percept_queue.put({"src": "APTITUDE", "score": score})
        log("AptitudeMonitor", f"aptitude engine sync -> score={score}%")
        with latency_lock:
            latency_log.append(("AptitudeMonitor", (time.perf_counter() - t0) * 1000))
        shutdown.wait(interval)


# ======================================================================
# CONSUMER WORKER : safely mutates shared_state under lock
# ======================================================================
def state_updater():
    while not shutdown.is_set() or not percept_queue.empty():
        try:
            p = percept_queue.get(timeout=0.3)
        except queue.Empty:
            continue
        with state_lock:                       # <-- critical section
            if p["src"] == "CODING":
                shared_state["problems_solved"] += p["solved"]
                shared_state["coding_score"] = p["score"]
            elif p["src"] == "APTITUDE":
                shared_state["aptitude_score"] = p["score"]
            elif p["src"] == "DRIVE":
                shared_state["open_drives"] += 1
            shared_state["updates_applied"] += 1
        log("StateUpdater", f"applied {p['src']} percept  (queue={percept_queue.qsize()})")
        percept_queue.task_done()


# ======================================================================
# MAIN EVENT LOOP  -- stays responsive the whole time
# ======================================================================
def main():
    print("=" * 84)
    print(" PLACEMENT PREP AGENT :: CONCURRENT DAEMON INFRASTRUCTURE (Assignment 2.1)")
    print("=" * 84 + "\n")

    workers = [
        threading.Thread(target=coding_platform_monitor, name="CodingMonitor", daemon=True),
        threading.Thread(target=placement_calendar_monitor, name="DriveMonitor", daemon=True),
        threading.Thread(target=aptitude_monitor, name="AptitudeMonitor", daemon=True),
        threading.Thread(target=state_updater, name="StateUpdater", daemon=True),
    ]
    for w in workers:
        w.start()
        log("MAIN", f"started daemon thread '{w.name}' (daemon={w.daemon})")

    print()
    # Main loop keeps running -- proves the UI/event loop is NOT blocked
    for cycle in range(1, 9):
        t0 = time.perf_counter()
        with state_lock:
            snap = dict(shared_state)
        log("MAIN-EVENTLOOP",
            f"cycle {cycle}: UI responsive | code={snap['coding_score']}% "
            f"apt={snap['aptitude_score']}% solved={snap['problems_solved']} "
            f"drives={snap['open_drives']}")
        with latency_lock:
            latency_log.append(("MAIN-EVENTLOOP", (time.perf_counter() - t0) * 1000))
        time.sleep(0.7)

    print("\n" + "-" * 84)
    log("MAIN", "shutdown signal issued to all daemons ...")
    shutdown.set()
    for w in workers:
        w.join(timeout=2.0)
        log("MAIN", f"thread '{w.name}' joined cleanly (alive={w.is_alive()})")

    with state_lock:
        final = dict(shared_state)

    print("\n" + "=" * 84)
    print(" FINAL SHARED STATE (no race conditions):")
    for k, v in final.items():
        print(f"   {k:<18} = {v}")

    print("\n EXECUTION LATENCY REPORT (ms):")
    agg = {}
    for name, ms in latency_log:
        agg.setdefault(name, []).append(ms)
    for name, vals in agg.items():
        print(f"   {name:<18} n={len(vals):<3} avg={sum(vals)/len(vals):.4f} "
              f"max={max(vals):.4f}")
    print("=" * 84)


if __name__ == "__main__":
    main()
