#!/usr/bin/env python3
"""
VCP Demo Runner v1.1
One-command demonstration of VeritasChain Protocol v1.1 capabilities.

This script demonstrates:
1. VCP v1.1 event generation (SIG → ORD → EXE lifecycle)
2. Policy Identification (REQUIRED in v1.1)
3. Hash chain construction (OPTIONAL in v1.1)
4. Merkle tree for external anchoring
5. Tamper detection capability
6. Third-party verification

Run: python run_demo.py

@copyright 2026 VeritasChain Standards Organization
@license Apache-2.0
"""

import json
import hashlib
import uuid
import time
import sys
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError
import subprocess
import threading
import signal

# Demo configuration
DEMO_ENDPOINT = "http://127.0.0.1:8765/ingest"
DEMO_TOKEN = "vcp-demo-token-2026"
DEMO_VENUE = "DEMO-VENUE"
DEMO_ACCOUNT = "acct:demo-trader-001"

# VCP v1.1 Policy Identification
DEMO_POLICY_ID = "org.veritaschain.demo:silver-demo-001"
DEMO_CONFORMANCE_TIER = "SILVER"
DEMO_ISSUER = "VeritasChain Standards Organization"


class VCPDemoSidecar:
    """VCP v1.1 compliant sidecar for demo purposes."""
    
    def __init__(self):
        self.endpoint = DEMO_ENDPOINT
        self.api_key = DEMO_TOKEN
        self.venue_id = DEMO_VENUE
        self.account_id = DEMO_ACCOUNT
        self._prev_hash = "0" * 64
        self.events: List[Dict] = []
        self._merkle_buffer: List[str] = []
        self._policy_effective_date = int(time.time() * 1e9)
    
    def _generate_uuid_v7(self) -> str:
        """Generate RFC 9562 UUID v7."""
        timestamp_ms = int(time.time() * 1000)
        timestamp_hex = format(timestamp_ms, '012x')
        random_part = uuid.uuid4().hex
        return f"{timestamp_hex[:8]}-{timestamp_hex[8:12]}-7{random_part[:3]}-{format(0x80, '02x')}{random_part[3:6]}-{random_part[6:18]}"
    
    def _compute_hash(self, event: Dict) -> str:
        """Compute SHA-256 hash with RFC 8785 canonicalization."""
        hashable = {"header": event["header"], "payload": event["payload"]}
        canonical = json.dumps(hashable, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical.encode()).hexdigest()
    
    def _get_policy_identification(self) -> Dict:
        """Generate VCP v1.1 Policy Identification block (REQUIRED)."""
        return {
            "version": "1.1",
            "policy_id": DEMO_POLICY_ID,
            "conformance_tier": DEMO_CONFORMANCE_TIER,
            "registration_policy": {
                "issuer": DEMO_ISSUER,
                "policy_uri": f"https://veritaschain.org/policies/{DEMO_POLICY_ID}",
                "effective_date": self._policy_effective_date
            },
            "verification_depth": {
                "hash_chain_validation": True,
                "merkle_proof_required": True,
                "external_anchor_required": True
            }
        }
    
    def _add_to_merkle_buffer(self, event_hash: str):
        """Add event hash to Merkle tree buffer."""
        self._merkle_buffer.append(event_hash)
    
    def get_merkle_root(self) -> Optional[str]:
        """Compute Merkle root from buffered event hashes."""
        if not self._merkle_buffer:
            return None
        hashes = self._merkle_buffer.copy()
        while len(hashes) > 1:
            if len(hashes) % 2 == 1:
                hashes.append(hashes[-1])
            new_hashes = []
            for i in range(0, len(hashes), 2):
                combined = hashes[i] + hashes[i + 1]
                new_hashes.append(hashlib.sha256(combined.encode()).hexdigest())
            hashes = new_hashes
        return hashes[0]
    
    def _create_event(self, event_type: str, event_type_code: int, 
                      trace_id: str, symbol: str, payload: Dict) -> Dict:
        """Create a VCP v1.1 event."""
        now = datetime.now(timezone.utc)
        event_id = self._generate_uuid_v7()
        
        event = {
            "header": {
                "event_id": event_id,
                "trace_id": trace_id,
                "timestamp_int": str(int(now.timestamp() * 1e9)),
                "timestamp_iso": now.isoformat(),
                "event_type": event_type,
                "event_type_code": event_type_code,
                "timestamp_precision": "MICROSECOND",
                "clock_sync_status": "NTP_SYNCED",
                "hash_algo": "SHA256",
                "venue_id": self.venue_id,
                "symbol": symbol,
                "account_id": self.account_id,
                "vcp_version": "1.1"
            },
            "payload": payload,
            "policy_identification": self._get_policy_identification()
        }
        
        event_hash = self._compute_hash(event)
        event["security"] = {
            "event_hash": event_hash,
            "prev_hash": self._prev_hash
        }
        self._prev_hash = event_hash
        self._add_to_merkle_buffer(event_hash)
        
        return event
    
    def emit_signal(self, symbol: str, algo_id: str, 
                    decision_factors: Optional[Dict] = None) -> str:
        """Emit a SIG event (VCP v1.1)."""
        now = datetime.now(timezone.utc)
        event_id = self._generate_uuid_v7()
        
        event = {
            "header": {
                "event_id": event_id,
                "trace_id": event_id,  # SIG event: trace_id = event_id
                "timestamp_int": str(int(now.timestamp() * 1e9)),
                "timestamp_iso": now.isoformat(),
                "event_type": "SIG",
                "event_type_code": 1,
                "timestamp_precision": "MICROSECOND",
                "clock_sync_status": "NTP_SYNCED",
                "hash_algo": "SHA256",
                "venue_id": self.venue_id,
                "symbol": symbol,
                "account_id": self.account_id,
                "vcp_version": "1.1"
            },
            "payload": {
                "vcp_gov": {
                    "algo_id": algo_id,
                    "algo_version": "1.0.0",
                    "decision_factors": decision_factors or {}
                }
            },
            "policy_identification": self._get_policy_identification()
        }
        
        event_hash = self._compute_hash(event)
        event["security"] = {
            "event_hash": event_hash,
            "prev_hash": self._prev_hash
        }
        self._prev_hash = event_hash
        self._add_to_merkle_buffer(event_hash)
        
        self.events.append(event)
        self._send(event)
        return event_id
    
    def emit_order(self, trace_id: str, symbol: str, order_id: str,
                   side: str, order_type: str, quantity: str, price: str) -> str:
        """Emit an ORD event (VCP v1.1)."""
        now = datetime.now(timezone.utc)
        event_id = self._generate_uuid_v7()
        
        event = {
            "header": {
                "event_id": event_id,
                "trace_id": trace_id,
                "timestamp_int": str(int(now.timestamp() * 1e9)),
                "timestamp_iso": now.isoformat(),
                "event_type": "ORD",
                "event_type_code": 2,
                "timestamp_precision": "MICROSECOND",
                "clock_sync_status": "NTP_SYNCED",
                "hash_algo": "SHA256",
                "venue_id": self.venue_id,
                "symbol": symbol,
                "account_id": self.account_id,
                "vcp_version": "1.1"
            },
            "payload": {
                "vcp_trade": {
                    "order_id": order_id,
                    "side": side,
                    "order_type": order_type,
                    "quantity": quantity,
                    "price": price,
                    "time_in_force": "GTC"
                }
            },
            "policy_identification": self._get_policy_identification()
        }
        
        event_hash = self._compute_hash(event)
        event["security"] = {
            "event_hash": event_hash,
            "prev_hash": self._prev_hash
        }
        self._prev_hash = event_hash
        self._add_to_merkle_buffer(event_hash)
        
        self.events.append(event)
        self._send(event)
        return event_id
    
    def emit_execution(self, trace_id: str, symbol: str, order_id: str,
                       exec_id: str, side: str, exec_price: str,
                       exec_quantity: str) -> str:
        """Emit an EXE event (VCP v1.1)."""
        now = datetime.now(timezone.utc)
        event_id = self._generate_uuid_v7()
        
        event = {
            "header": {
                "event_id": event_id,
                "trace_id": trace_id,
                "timestamp_int": str(int(now.timestamp() * 1e9)),
                "timestamp_iso": now.isoformat(),
                "event_type": "EXE",
                "event_type_code": 5,
                "timestamp_precision": "MICROSECOND",
                "clock_sync_status": "NTP_SYNCED",
                "hash_algo": "SHA256",
                "venue_id": self.venue_id,
                "symbol": symbol,
                "account_id": self.account_id,
                "vcp_version": "1.1"
            },
            "payload": {
                "vcp_trade": {
                    "order_id": order_id,
                    "exec_id": exec_id,
                    "side": side,
                    "exec_price": exec_price,
                    "exec_quantity": exec_quantity,
                    "commission": "0"
                }
            },
            "policy_identification": self._get_policy_identification()
        }
        
        event_hash = self._compute_hash(event)
        event["security"] = {
            "event_hash": event_hash,
            "prev_hash": self._prev_hash
        }
        self._prev_hash = event_hash
        self._add_to_merkle_buffer(event_hash)
        
        self.events.append(event)
        self._send(event)
        return event_id
    
    def _send(self, event: Dict) -> bool:
        """Send event to mock server."""
        try:
            data = json.dumps(event).encode()
            req = Request(
                self.endpoint,
                data=data,
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {self.api_key}'
                }
            )
            with urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except Exception as e:
            print(f"  [!] Send failed: {e}")
            return False


def verify_chain(events: List[Dict], show_details: bool = True) -> bool:
    """Verify hash chain integrity."""
    if show_details:
        print()
        print("=" * 60)
        print("HASH CHAIN VERIFICATION")
        print("=" * 60)
    
    all_valid = True
    prev_hash = "0" * 64
    
    for i, event in enumerate(events):
        # Recompute hash
        hashable = {"header": event["header"], "payload": event["payload"]}
        canonical = json.dumps(hashable, sort_keys=True, separators=(',', ':'))
        computed = hashlib.sha256(canonical.encode()).hexdigest()
        
        stored = event["security"]["event_hash"]
        stored_prev = event["security"]["prev_hash"]
        
        hash_valid = computed == stored
        chain_valid = stored_prev == prev_hash
        
        if show_details:
            event_type = event["header"]["event_type"]
            status = "✓" if (hash_valid and chain_valid) else "✗"
            print(f"  [{i}] {event_type}  Hash: {'OK' if hash_valid else 'FAIL'}  Chain: {'OK' if chain_valid else 'FAIL'}  {status}")
        
        if not hash_valid or not chain_valid:
            all_valid = False
        
        prev_hash = stored
    
    if show_details:
        print()
        if all_valid:
            print("  Result: ✓ CHAIN INTEGRITY VERIFIED")
        else:
            print("  Result: ✗ CHAIN INTEGRITY FAILED")
        print()
    
    return all_valid


def tamper_event(event: Dict, field: str = "quantity") -> Dict:
    """Create a tampered copy of an event."""
    import copy
    tampered = copy.deepcopy(event)
    
    if "vcp_trade" in tampered["payload"]:
        if field in tampered["payload"]["vcp_trade"]:
            original = tampered["payload"]["vcp_trade"][field]
            tampered["payload"]["vcp_trade"][field] = "999999"  # Tampered value
            return tampered, original
    
    return tampered, None


def run_demo():
    """Main demo execution."""
    print()
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 10 + "VeritasChain Protocol (VCP) v1.1 Demo" + " " * 10 + "║")
    print("║" + " " * 18 + "\"Verify, Don't Trust\"" + " " * 18 + "║")
    print("╚" + "═" * 58 + "╝")
    print()
    
    # Check if mock server is running
    print("[1/6] Checking mock server...")
    try:
        req = Request("http://127.0.0.1:8765/health")
        with urlopen(req, timeout=2) as resp:
            if resp.status == 200:
                print("  ✓ Mock server is running")
    except:
        print("  Starting mock server in background...")
        # Start mock server
        server_script = os.path.join(os.path.dirname(__file__), "mock_server.py")
        subprocess.Popen(
            [sys.executable, server_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(1)
        print("  ✓ Mock server started")
    
    print()
    print("[2/6] Generating VCP v1.1 events (trade lifecycle)...")
    print()
    
    sidecar = VCPDemoSidecar()
    
    # Simulate a trade lifecycle
    print("  Scenario: USDJPY Buy Order")
    print("  Policy ID:", DEMO_POLICY_ID)
    print("  Conformance Tier:", DEMO_CONFORMANCE_TIER)
    print("  " + "-" * 40)
    
    # Signal
    print("  → Generating SIG (Algorithm Signal)...")
    trace_id = sidecar.emit_signal(
        symbol="USDJPY",
        algo_id="momentum-algo-v2",
        decision_factors={
            "rsi": "32.5",
            "macd_signal": "bullish",
            "confidence": "0.87"
        }
    )
    print(f"    trace_id: {trace_id[:20]}...")
    time.sleep(0.1)
    
    # Order
    print("  → Generating ORD (Order Submission)...")
    sidecar.emit_order(
        trace_id=trace_id,
        symbol="USDJPY",
        order_id="ORD-2026-001",
        side="BUY",
        order_type="LIMIT",
        quantity="100000",
        price="157.250"
    )
    time.sleep(0.1)
    
    # Execution
    print("  → Generating EXE (Execution Report)...")
    sidecar.emit_execution(
        trace_id=trace_id,
        symbol="USDJPY",
        order_id="ORD-2026-001",
        exec_id="EXE-2026-001",
        side="BUY",
        exec_price="157.248",
        exec_quantity="100000"
    )
    
    print()
    print(f"  ✓ Generated {len(sidecar.events)} events")
    
    # Verify original chain
    print()
    print("[3/6] Verifying hash chain integrity...")
    original_valid = verify_chain(sidecar.events)
    
    # Merkle Root for External Anchoring (NEW in v1.1)
    print()
    print("[4/6] Computing Merkle Root for External Anchoring...")
    merkle_root = sidecar.get_merkle_root()
    print(f"  Merkle Root: {merkle_root[:16]}...{merkle_root[-16:]}")
    print("  ✓ Ready for external anchor (TSA/Blockchain)")
    print("  Note: Silver tier requires anchoring every 24 hours")
    
    # Tamper detection demo
    print()
    print("[5/6] Demonstrating tamper detection...")
    print()
    print("  Simulating data manipulation attack:")
    print("  " + "-" * 40)
    
    # Create tampered copy
    tampered_events = sidecar.events.copy()
    tampered_event, original_value = tamper_event(tampered_events[1])
    tampered_events[1] = tampered_event
    
    print(f"  → Original quantity: {original_value}")
    print(f"  → Tampered quantity: 999999")
    print()
    print("  Verifying tampered chain...")
    
    tampered_valid = verify_chain(tampered_events)
    
    if not tampered_valid:
        print("  ✓ Tampering detected (verification failed).")
    
    # Export events
    print()
    print("[6/6] Exporting events for external verification...")
    
    export_path = os.path.join(os.path.dirname(__file__), "sample_events.jsonl")
    with open(export_path, 'w') as f:
        for event in sidecar.events:
            f.write(json.dumps(event) + '\n')
    
    print(f"  ✓ Exported to: demo/sample_events.jsonl")
    print()
    print("  You can verify with:")
    print(f"    python ../tools/vcp_verifier.py {export_path}")
    
    # Summary
    print()
    print("=" * 60)
    print("VCP v1.1 DEMO COMPLETE")
    print("=" * 60)
    print()
    print("  What you've seen (VCP v1.1):")
    print("  ┌─────────────────────────────────────────────────────┐")
    print("  │ 1. Policy Identification in every event (REQUIRED) │")
    print("  │ 2. Cryptographic hash chain (OPTIONAL in v1.1)     │")
    print("  │ 3. Merkle Root for External Anchoring (REQUIRED)   │")
    print("  │ 4. Tamper detection via hash verification          │")
    print("  │ 5. Third-party verifiable without trust            │")
    print("  └─────────────────────────────────────────────────────┘")
    print()
    print("  VCP v1.1 Key Changes:")
    print("  • Policy Identification: REQUIRED for all events")
    print("  • External Anchor: REQUIRED for all tiers")
    print("  • Hash Chain (PrevHash): Now OPTIONAL")
    print()
    print("  This is the foundation of \"Verify, Don't Trust\"")
    print()
    print("  For production access:")
    print("  → Contact: enterprise@veritaschain.org")
    print("  → Website: https://veritaschain.org")
    print()
    print("=" * 60)
    print()


if __name__ == "__main__":
    run_demo()
