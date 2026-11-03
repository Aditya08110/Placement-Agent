"""
Assignment 2.2 : Distributed Agent Messaging using Sockets  --  AGENT-B (SERVER)
Project: Placement Preparation Agent
------------------------------------------------------------------
AGENT-B = "Placement Cell Agent". Listens on a TCP socket, ingests
serialized (JSON) state payloads from Agent-A (the Student Prep Agent),
reasons over them, and replies autonomously with company eligibility.

TERMINAL 1:  python agent_b_server.py
TERMINAL 2:  python agent_a_client.py
"""

import socket
import json
import struct
import threading
from datetime import datetime

HOST, PORT = "127.0.0.1", 50607

# ---------------- Agent-B's own knowledge base ------------------------
COMPANY_DB = [
    {"name": "Amazon",      "cgpa": 8.0, "coding": 85, "aptitude": 80, "package": 44.0},
    {"name": "Zoho",        "cgpa": 7.0, "coding": 75, "aptitude": 70, "package": 18.0},
    {"name": "Freshworks",  "cgpa": 7.5, "coding": 78, "aptitude": 72, "package": 22.0},
    {"name": "Infosys",     "cgpa": 6.5, "coding": 55, "aptitude": 60, "package": 6.5},
    {"name": "TCS Digital", "cgpa": 6.0, "coding": 50, "aptitude": 65, "package": 7.0},
    {"name": "Wipro",       "cgpa": 6.0, "coding": 45, "aptitude": 55, "package": 5.5},
]


# ============ LENGTH-PREFIXED FRAMING (serialization transport) ========
def send_msg(sock, obj):
    """Serialize dict -> JSON -> utf-8, prefixed with 4-byte big-endian length."""
    data = json.dumps(obj).encode("utf-8")
    sock.sendall(struct.pack(">I", len(data)) + data)


def recv_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


def recv_msg(sock):
    """Read 4-byte header then exactly that many bytes; deserialize JSON."""
    hdr = recv_exact(sock, 4)
    if not hdr:
        return None
    (length,) = struct.unpack(">I", hdr)
    body = recv_exact(sock, length)
    if body is None:
        return None
    return json.loads(body.decode("utf-8"))


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [AGENT-B/SERVER] {msg}")


# ============ AGENT-B AUTONOMOUS REASONING =============================
def evaluate_eligibility(profile):
    eligible, blocked = [], []
    for c in COMPANY_DB:
        reasons = []
        if profile["cgpa"] < c["cgpa"]:
            reasons.append(f"CGPA {profile['cgpa']}<{c['cgpa']}")
        if profile["coding_score"] < c["coding"]:
            reasons.append(f"coding {profile['coding_score']}<{c['coding']}")
        if profile["aptitude_score"] < c["aptitude"]:
            reasons.append(f"aptitude {profile['aptitude_score']}<{c['aptitude']}")
        if reasons:
            blocked.append({"company": c["name"], "gaps": reasons})
        else:
            eligible.append({"company": c["name"], "package_lpa": c["package"]})
    eligible.sort(key=lambda x: -x["package_lpa"])
    return eligible, blocked


def handle_message(msg):
    """Proactive remote message handling -- act on payload 'intent'."""
    intent = msg.get("intent")
    log(f"ingested payload intent='{intent}' from '{msg.get('sender')}'")

    if intent == "HANDSHAKE":
        return {"intent": "HANDSHAKE_ACK", "sender": "AGENT-B",
                "status": "OK", "protocol": "PPA/1.0"}

    if intent == "SYNC_STATE":
        p = msg["payload"]
        eligible, blocked = evaluate_eligibility(p)
        log(f"reasoned -> {len(eligible)} eligible / {len(blocked)} blocked")
        top_gap = max(blocked, key=lambda b: len(b["gaps"]))["gaps"] if blocked else []
        return {
            "intent": "ELIGIBILITY_REPORT",
            "sender": "AGENT-B",
            "payload": {
                "eligible": eligible,
                "blocked": blocked,
                "advice": ("Focus on: " + ", ".join(sorted({g.split()[0] for b in blocked
                                                            for g in b["gaps"]})))
                          if blocked else "All drives unlocked."
            },
        }

    if intent == "REQUEST_ACTION":
        return {"intent": "ACTION_DIRECTIVE", "sender": "AGENT-B",
                "payload": {"directive": "SCHEDULE_MOCK_INTERVIEW",
                            "slot": "2026-09-12 10:00 IST"}}

    if intent == "TERMINATE":
        return {"intent": "TERMINATE_ACK", "sender": "AGENT-B"}

    return {"intent": "ERROR", "sender": "AGENT-B", "reason": "unknown intent"}


def serve_client(conn, addr):
    log(f"connection accepted from {addr}")
    with conn:
        while True:
            msg = recv_msg(conn)
            if msg is None:
                break
            reply = handle_message(msg)
            send_msg(conn, reply)
            log(f"dispatched reply intent='{reply['intent']}'")
            if msg.get("intent") == "TERMINATE":
                break
    log(f"connection with {addr} closed")


def main():
    print("=" * 78)
    print(" AGENT-B :: PLACEMENT CELL AGENT (socket server)  [Assignment 2.2]")
    print("=" * 78)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen(5)
        log(f"listening on {HOST}:{PORT} ...")
        while True:
            conn, addr = s.accept()
            threading.Thread(target=serve_client, args=(conn, addr), daemon=True).start()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("server shutdown")
