#!/usr/bin/env python3
"""
VCP Hash Chain Verifier v1.0
Verifies hash chain integrity for VCP events.

@copyright 2026 VeritasChain Standards Organization
@license Apache-2.0
"""

import json
import hashlib
import sys


def compute_hash(event: dict) -> str:
    """Compute SHA-256 hash (RFC 8785 canonicalization)"""
    hashable = {"header": event["header"], "payload": event["payload"]}
    canonical = json.dumps(hashable, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode()).hexdigest()


def verify_chain(events: list) -> bool:
    """Verify hash chain integrity"""
    print("=" * 60)
    print("VCP Hash Chain Verification Report")
    print("=" * 60)
    print()
    print(f"Input Events: {len(events)}")
    
    if events:
        print(f"Trace ID: {events[0]['header'].get('trace_id', 'N/A')}")
    
    print()
    print("Event Chain:")
    print("-" * 60)
    
    all_valid = True
    prev_hash = "0" * 64
    
    for i, event in enumerate(events):
        event_id = event["header"]["event_id"][:30] + "..."
        event_type = event["header"]["event_type"]
        
        computed = compute_hash(event)
        stored = event["security"]["event_hash"]
        hash_valid = computed == stored
        
        stored_prev = event["security"]["prev_hash"]
        chain_valid = stored_prev == prev_hash
        
        hash_status = "VALID" if hash_valid else "INVALID"
        chain_status = "VALID" if chain_valid else "INVALID"
        
        print(f"  [{i}] {event_type}   {event_id}")
        print(f"       Hash: {hash_status}    Chain: {chain_status}")
        
        if not hash_valid or not chain_valid:
            all_valid = False
        
        prev_hash = stored
    
    print("-" * 60)
    print()
    
    if all_valid:
        print("Chain Integrity: VERIFIED")
    else:
        print("Chain Integrity: FAILED")
    
    print()
    print("=" * 60)
    
    return all_valid


def main():
    if len(sys.argv) < 2:
        print("Usage: python vcp_verifier.py <events.jsonl>")
        sys.exit(1)
    
    events = []
    with open(sys.argv[1], 'r') as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))
    
    valid = verify_chain(events)
    sys.exit(0 if valid else 1)


if __name__ == "__main__":
    main()
