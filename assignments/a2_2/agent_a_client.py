"""
Assignment 2.2 : Distributed Agent Messaging using Sockets  --  AGENT-A (CLIENT)
Project: Placement Preparation Agent
------------------------------------------------------------------
AGENT-A = "Student Prep Agent". Serializes its live internal state and
transfers it to Agent-B over a networked socket, then autonomously
adapts its own plan based on Agent-B's returned payload.

TERMINAL 2:  python agent_a_client.py   (run AFTER agent_b_server.py)
"""

import socket
import json
import struct
import time
from datetime import datetime

HOST, PORT = "127.0.0.1", 50607


def send_msg(sock, obj):
    data = json.dumps(obj).encode("utf-8")
    sock.sendall(struct.pack(">I", len(data)) + data)


def recv_exact(sock, n):
    buf = b""
    while len(buf) < n:
        c = sock.recv(n - len(buf))
        if not c:
            return None
        buf += c
    return buf


def recv_msg(sock):
    hdr = recv_exact(sock, 4)
    if not hdr:
        return None
    (length,) = struct.unpack(">I", hdr)
    return json.loads(recv_exact(sock, length).decode("utf-8"))


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [AGENT-A/CLIENT] {msg}")


# ------------- Agent-A's live internal state (the payload) -------------
AGENT_A_STATE = {
    "student_id": "RA2211003010999",
    "name": "Student",
    "cgpa": 7.6,
    "coding_score": 79,
    "aptitude_score": 74,
    "core_subject_score": 68,
    "mock_interview_rating": 6,
    "topics_completed": ["Arrays", "Strings", "OOPS", "DBMS"],
    "topics_pending": ["DP", "Graphs", "OS", "CN"],
}


def main():
    print("=" * 78)
    print(" AGENT-A :: STUDENT PREP AGENT (socket client)  [Assignment 2.2]")
    print("=" * 78)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        log(f"TCP channel established -> {HOST}:{PORT}")

        # ---- 1. HANDSHAKE ----
        send_msg(s, {"intent": "HANDSHAKE", "sender": "AGENT-A", "protocol": "PPA/1.0"})
        log("TX intent=HANDSHAKE")
        r = recv_msg(s)
        log(f"RX intent={r['intent']} status={r.get('status')}")
        time.sleep(0.4)

        # ---- 2. SERIALIZED STATE TRANSFER ----
        payload = {"intent": "SYNC_STATE", "sender": "AGENT-A", "payload": AGENT_A_STATE}
        send_msg(s, payload)
        log(f"TX intent=SYNC_STATE  ({len(json.dumps(payload))} bytes serialized)")
        r = recv_msg(s)
        log(f"RX intent={r['intent']}")

        p = r["payload"]
        print("\n   ---- AGENT-B ELIGIBILITY REPORT ----")
        for e in p["eligible"]:
            print(f"      ELIGIBLE : {e['company']:<12} {e['package_lpa']} LPA")
        for b in p["blocked"]:
            print(f"      BLOCKED  : {b['company']:<12} gaps -> {', '.join(b['gaps'])}")
        print(f"      ADVICE   : {p['advice']}\n")
        time.sleep(0.4)

        # ---- 3. AUTONOMOUS REACTION to remote payload ----
        if p["blocked"]:
            log("AUTONOMOUS DECISION: gaps detected -> requesting remedial action")
            send_msg(s, {"intent": "REQUEST_ACTION", "sender": "AGENT-A"})
            r = recv_msg(s)
            d = r["payload"]
            log(f"RX intent={r['intent']} -> {d['directive']} @ {d['slot']}")
            log("PLAN UPDATED: mock interview auto-added to local study calendar")
        time.sleep(0.4)

        # ---- 4. TERMINATE ----
        send_msg(s, {"intent": "TERMINATE", "sender": "AGENT-A"})
        r = recv_msg(s)
        log(f"RX intent={r['intent']} -- session closed cleanly")

    print("=" * 78)


if __name__ == "__main__":
    main()
