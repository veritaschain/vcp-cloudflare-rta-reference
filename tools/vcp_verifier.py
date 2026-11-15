#!/usr/bin/env python3
"""
Local hash-chain checker for this historical VCP reference PoC.

A match is limited to the stored header/payload hashes and hash links. This
tool does not authenticate signatures, policy fields, anchors or completeness.

@copyright 2026 VeritasChain Standards Organization
@license Apache-2.0
"""

import argparse
import json
import hashlib
import math
import re
import sys


def _object_without_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON member")
        result[key] = value
    return result


def _reject_constant(_value):
    raise ValueError("Nonfinite JSON number")


def _finite_float(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Nonfinite JSON number")
    return result


def read_events(path):
    """Read JSONL without silently choosing between duplicate field values."""
    with open(path, 'r', encoding='utf-8') as stream:
        return [json.loads(line, object_pairs_hook=_object_without_duplicates,
                           parse_constant=_reject_constant,
                           parse_float=_finite_float)
                for line in stream if line.strip()]


def _validate_event(event):
    """Check only the shape needed by this checker, not a normative VCP schema."""
    if not isinstance(event, dict):
        raise ValueError("Event must be an object")
    for field in ('header', 'payload', 'security'):
        if not isinstance(event.get(field), dict):
            raise ValueError("Required event object is missing or malformed")
    for field in ('event_id', 'event_type'):
        value = event['header'].get(field)
        if not isinstance(value, str) or not value:
            raise ValueError("Required event label is missing or malformed")
    for field in ('event_hash', 'prev_hash'):
        value = event['security'].get(field)
        if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value):
            raise ValueError("Required stored hash is missing or malformed")
    # Also reject nonfinite values supplied directly through the Python API.
    json.dumps(event, allow_nan=False)


def compute_hash(event: dict) -> str:
    """Preserve this PoC's Python JSON bytes; this is not RFC 8785 JCS."""
    hashable = {"header": event["header"], "payload": event["payload"]}
    canonical = json.dumps(hashable, sort_keys=True, separators=(',', ':'),
                           allow_nan=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def verify_chain(events: list) -> bool:
    """Return True only for a nonempty, well-formed local hash-chain match."""
    print("=" * 60)
    print("VCP Hash Chain Verification Report")
    print("=" * 60)
    print()
    if not isinstance(events, list):
        print("Chain Integrity: FAILED (events must be a list)")
        return False
    print(f"Input Events: {len(events)}")
    print("Scope: header/payload hashes and adjacent stored hash links only.")
    print("Not assessed: signatures, policy fields, anchors or history completeness.")
    if not events:
        print("Chain Integrity: INDETERMINATE (no events supplied)")
        return False
    
    print()
    print("Event Chain:")
    print("-" * 60)
    
    all_valid = True
    prev_hash = "0" * 64
    
    for i, event in enumerate(events):
        try:
            _validate_event(event)
            computed = compute_hash(event)
        except (ValueError, TypeError, KeyError, RecursionError, OverflowError):
            print(f"  [{i}] INVALID EVENT INPUT")
            all_valid = False
            prev_hash = None
            continue
        event_id = event["header"]["event_id"][:30] + "..."
        event_type = event["header"]["event_type"]
        
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
        print("Chain Integrity: MATCH (local hash checks only)")
    else:
        print("Chain Integrity: FAILED")
    
    print()
    print("=" * 60)
    
    return all_valid


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('events', help='Local JSONL event file')
    args = parser.parse_args(argv)
    try:
        events = read_events(args.events)
    except OSError:
        print("Event input unavailable.", file=sys.stderr)
        return 2
    except (ValueError, UnicodeError, RecursionError, OverflowError):
        print("Invalid JSONL event input.", file=sys.stderr)
        return 1
    valid = verify_chain(events)
    return 2 if not events else (0 if valid else 1)


if __name__ == "__main__":
    sys.exit(main())
