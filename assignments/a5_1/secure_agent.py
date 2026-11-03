"""
Assignment 5.1 : Agent Authentication and Host Integrity Verification
Project: Placement Preparation Agent
------------------------------------------------------------------
Security layer for the agent's message pipeline:
  * HMAC-SHA256 digital signature over every command payload
  * Public-key style trusted-host registry (host_id -> shared secret)
  * Nonce + timestamp replay-attack window
  * Host allow-list (origin integrity verification)
  * Constant-time comparison to prevent timing side-channels

Then simulates 6 attack scenarios and shows each being rejected.

Run:  python secure_agent.py
"""

import hmac
import hashlib
import json
import time
import secrets
from datetime import datetime

def log(tag, msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [{tag:<12}] {msg}")


# ======================================================================
# 1. TRUSTED HOST REGISTRY  (key management)
# ======================================================================
TRUSTED_HOSTS = {
    "placement-cell-01": {"secret": b"K3y_PlacementCell_2026_A9f2", "ip": "127.0.0.1",
                          "role": "ADMIN"},
    "mentor-node-07":    {"secret": b"K3y_MentorNode_2026_B7x4",    "ip": "127.0.0.1",
                          "role": "TRAINER"},
    "student-agent-a":   {"secret": b"K3y_StudentAgent_2026_C1m8",  "ip": "127.0.0.1",
                          "role": "PEER"},
}

ROLE_PERMISSIONS = {
    "ADMIN":   {"UPDATE_PLAN", "PUSH_DRIVE", "WIPE_PROFILE", "SYNC_STATE"},
    "TRAINER": {"UPDATE_PLAN", "SYNC_STATE"},
    "PEER":    {"SYNC_STATE"},
}

REPLAY_WINDOW_SEC = 30
SEEN_NONCES = set()


# ======================================================================
# 2. SIGNING (sender side)
# ======================================================================
def canonical(payload: dict) -> bytes:
    """Deterministic serialization -- signature must be order-independent."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def sign_message(host_id, command, args, secret=None):
    secret = secret or TRUSTED_HOSTS.get(host_id, {}).get("secret", b"")
    body = {
        "host_id": host_id,
        "command": command,
        "args": args,
        "nonce": secrets.token_hex(8),
        "timestamp": int(time.time()),
    }
    sig = hmac.new(secret, canonical(body), hashlib.sha256).hexdigest()
    return {"body": body, "signature": sig}


# ======================================================================
# 3. VERIFICATION PIPELINE (receiver side) -- 6 sequential gates
# ======================================================================
class SecurityException(Exception):
    pass


class SecureAgentGateway:
    def __init__(self, ip_allowlist=("127.0.0.1",)):
        self.allow = set(ip_allowlist)
        self.accepted = 0
        self.rejected = 0
        self.audit = []

    def _reject(self, gate, reason):
        self.rejected += 1
        self.audit.append(("REJECT", gate, reason))
        log("SECURITY", f"  X GATE-{gate} FAILED -> {reason}")
        raise SecurityException(f"[GATE-{gate}] {reason}")

    def verify(self, msg, src_ip="127.0.0.1"):
        body = msg.get("body", {})
        sig = msg.get("signature", "")
        hid = body.get("host_id")

        # ---- GATE 1 : structural integrity ---------------------------
        for f in ("host_id", "command", "args", "nonce", "timestamp"):
            if f not in body:
                self._reject(1, f"malformed payload, missing field '{f}'")
        log("SECURITY", "  OK GATE-1 payload structure valid")

        # ---- GATE 2 : host identity is known -------------------------
        if hid not in TRUSTED_HOSTS:
            self._reject(2, f"unknown host_id '{hid}' -- not in trusted registry")
        host = TRUSTED_HOSTS[hid]
        log("SECURITY", f"  OK GATE-2 host '{hid}' found in trusted registry (role={host['role']})")

        # ---- GATE 3 : host integrity / origin IP ---------------------
        if src_ip not in self.allow or src_ip != host["ip"]:
            self._reject(3, f"host integrity violation: '{hid}' claimed from {src_ip}, "
                            f"registered {host['ip']}")
        log("SECURITY", f"  OK GATE-3 origin IP {src_ip} matches registered host")

        # ---- GATE 4 : cryptographic signature ------------------------
        expected = hmac.new(host["secret"], canonical(body), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):     # constant-time
            self._reject(4, f"HMAC-SHA256 signature mismatch "
                            f"(expected {expected[:16]}..., got {sig[:16] or 'EMPTY'}...)")
        log("SECURITY", f"  OK GATE-4 signature verified {sig[:16]}...")

        # ---- GATE 5 : replay / freshness -----------------------------
        age = int(time.time()) - body["timestamp"]
        if abs(age) > REPLAY_WINDOW_SEC:
            self._reject(5, f"stale message: age {age}s exceeds {REPLAY_WINDOW_SEC}s window")
        if body["nonce"] in SEEN_NONCES:
            self._reject(5, f"REPLAY ATTACK: nonce {body['nonce']} already consumed")
        SEEN_NONCES.add(body["nonce"])
        log("SECURITY", f"  OK GATE-5 freshness ok (age={age}s), nonce unique")

        # ---- GATE 6 : authorization (role -> command) ----------------
        allowed = ROLE_PERMISSIONS[host["role"]]
        if body["command"] not in allowed:
            self._reject(6, f"PRIVILEGE ESCALATION: role '{host['role']}' may not "
                            f"execute '{body['command']}' (allowed: {sorted(allowed)})")
        log("SECURITY", f"  OK GATE-6 role '{host['role']}' authorized for '{body['command']}'")

        self.accepted += 1
        self.audit.append(("ACCEPT", 0, f"{hid}:{body['command']}"))
        return body

    # ---------------- protected agent action ---------------------------
    def execute(self, msg, src_ip="127.0.0.1"):
        try:
            body = self.verify(msg, src_ip)
            log("AGENT", f"  >> EXECUTING '{body['command']}' args={body['args']}")
            return True
        except SecurityException as e:
            log("AGENT", f"  >> COMMAND BLOCKED. Agent state unchanged. {e}")
            return False


# ======================================================================
# 4. ATTACK SIMULATIONS
# ======================================================================
def sep(t):
    print("\n" + "=" * 90); print(f" {t}"); print("=" * 90)


def scenario(n, title):
    print(f"\n--- SCENARIO {n}: {title} " + "-" * max(0, 60 - len(title)))


def main():
    sep("AGENT AUTHENTICATION & HOST INTEGRITY VERIFICATION (Assignment 5.1)")
    gw = SecureAgentGateway()
    print(f" Trusted hosts     : {list(TRUSTED_HOSTS)}")
    print(f" Signature scheme  : HMAC-SHA256 over canonical JSON")
    print(f" Replay window     : {REPLAY_WINDOW_SEC}s + single-use nonce")
    print(f" Verification gates: 6 (structure, identity, origin, signature, freshness, authz)")

    # ---------- LEGITIMATE ----------
    scenario(1, "LEGITIMATE command from trusted ADMIN host")
    good = sign_message("placement-cell-01", "PUSH_DRIVE",
                        {"company": "Amazon", "date": "2026-09-15"})
    gw.execute(good)

    scenario(2, "LEGITIMATE command from TRAINER host")
    good2 = sign_message("mentor-node-07", "UPDATE_PLAN", {"add_topic": "Graphs"})
    gw.execute(good2)

    # ---------- ATTACKS ----------
    scenario(3, "ATTACK - forged signature (attacker guesses the key)")
    forged = sign_message("placement-cell-01", "WIPE_PROFILE", {"target": "all"},
                          secret=b"WRONG_KEY_GUESSED_BY_ATTACKER")
    gw.execute(forged)

    scenario(4, "ATTACK - unknown/unregistered rogue host")
    rogue = sign_message("evil-node-99", "WIPE_PROFILE", {"target": "all"},
                         secret=b"whatever")
    rogue["body"]["host_id"] = "evil-node-99"
    gw.execute(rogue)

    scenario(5, "ATTACK - tampered payload (man-in-the-middle mutation)")
    tampered = sign_message("mentor-node-07", "UPDATE_PLAN", {"add_topic": "Graphs"})
    tampered["body"]["args"] = {"add_topic": "Graphs", "delete_all_progress": True}
    log("ATTACKER", "  intercepted message and injected 'delete_all_progress': True")
    gw.execute(tampered)

    scenario(6, "ATTACK - replay of a previously valid message")
    log("ATTACKER", "  re-sending the captured Scenario-1 packet verbatim")
    gw.execute(good)

    scenario(7, "ATTACK - privilege escalation by a low-privilege PEER")
    esc = sign_message("student-agent-a", "WIPE_PROFILE", {"target": "rival-student"})
    gw.execute(esc)

    scenario(8, "ATTACK - host spoofing from a non-registered IP")
    spoof = sign_message("placement-cell-01", "PUSH_DRIVE", {"company": "Fake Inc"})
    gw.execute(spoof, src_ip="203.0.113.66")

    scenario(9, "ATTACK - stale/expired message (clock rollback)")
    stale = sign_message("placement-cell-01", "PUSH_DRIVE", {"company": "Old Corp"})
    stale["body"]["timestamp"] -= 9999
    stale["signature"] = hmac.new(TRUSTED_HOSTS["placement-cell-01"]["secret"],
                                  canonical(stale["body"]), hashlib.sha256).hexdigest()
    gw.execute(stale)

    scenario(10, "ATTACK - malformed / fuzzing payload")
    gw.execute({"body": {"command": "SYNC_STATE"}, "signature": ""})

    # ---------- AUDIT ----------
    sep("SECURITY AUDIT LOG")
    print(f" {'Result':<9}{'Gate':<7}Detail")
    for res, gate, detail in gw.audit:
        print(f" {res:<9}{('-' if gate == 0 else 'GATE-'+str(gate)):<7}{detail}")
    print("-" * 90)
    print(f" ACCEPTED : {gw.accepted}   REJECTED : {gw.rejected}   "
          f"BLOCK RATE : {gw.rejected/(gw.accepted+gw.rejected)*100:.1f}%")
    print(" RESULT   : all unauthorized commands blocked; agent state never mutated.")
    print("=" * 90)


if __name__ == "__main__":
    main()
