# VCP Demo - Local Proof of Concept

**Experience the VeritasChain Protocol without NDA credentials**

## Quick Start

```bash
# Run the complete demo
python run_demo.py
```

That's it! The demo will:
1. Start a local mock server (if not running)
2. Generate a complete trade lifecycle (SIG → ORD → EXE)
3. Build a cryptographic hash chain
4. Demonstrate tamper detection
5. Export verifiable event data

## What You'll See

```
╔══════════════════════════════════════════════════════════╗
║            VeritasChain Protocol (VCP) Demo              ║
║                  "Verify, Don't Trust"                   ║
╚══════════════════════════════════════════════════════════╝

[1/5] Checking mock server...
  ✓ Mock server is running

[2/5] Generating VCP events (trade lifecycle)...
  Scenario: USDJPY Buy Order
  ----------------------------------------
  → Generating SIG (Algorithm Signal)...
  → Generating ORD (Order Submission)...
  → Generating EXE (Execution Report)...
  ✓ Generated 3 events

[3/5] Verifying hash chain integrity...
  [0] SIG  Hash: OK  Chain: OK  ✓
  [1] ORD  Hash: OK  Chain: OK  ✓
  [2] EXE  Hash: OK  Chain: OK  ✓
  Result: ✓ CHAIN INTEGRITY VERIFIED

[4/5] Demonstrating tamper detection...
  → Original quantity: 100000
  → Tampered quantity: 999999
  [0] SIG  Hash: OK  Chain: OK  ✓
  [1] ORD  Hash: FAIL  Chain: OK  ✗
  [2] EXE  Hash: OK  Chain: FAIL  ✗
  Result: ✗ CHAIN INTEGRITY FAILED
  ✓ TAMPER DETECTED! Manipulation attempt blocked.
```

## Files

| File | Description |
|------|-------------|
| `run_demo.py` | Main demo script - run this |
| `mock_server.py` | Local HTTP server simulating VCP Cloud |
| `sample_events.jsonl` | Generated events (after running demo) |

## Manual Verification

After running the demo, verify the exported events:

```bash
python ../tools/vcp_verifier.py sample_events.jsonl
```

## Understanding the Demo

### Event Types

| Type | Code | Description |
|------|------|-------------|
| SIG | 1 | Algorithm generates trading signal |
| ORD | 2 | Order submitted to venue |
| EXE | 5 | Order executed (filled) |

### Hash Chain Structure

```
Event 0 (SIG)          Event 1 (ORD)          Event 2 (EXE)
┌─────────────┐        ┌─────────────┐        ┌─────────────┐
│ event_hash  │───────▶│ prev_hash   │        │             │
│   abc123... │        │   abc123... │───────▶│ prev_hash   │
└─────────────┘        │ event_hash  │        │   def456... │
                       │   def456... │        │ event_hash  │
                       └─────────────┘        │   ghi789... │
                                              └─────────────┘
```

Each event's hash becomes the `prev_hash` of the next event, creating an unbreakable chain.

### Why Tamper Detection Works

When Event 1's data is modified:
- Its computed hash no longer matches the stored `event_hash`
- Event 2's `prev_hash` no longer matches Event 1's actual hash
- **Both failures are detected, pinpointing the tampered event**

## Mock Server API

Start the server manually:

```bash
python mock_server.py
```

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | API documentation |
| GET | `/health` | Health check |
| GET | `/events` | List received events |
| GET | `/events/export` | Download events as JSONL |
| POST | `/ingest` | Submit VCP event |
| DELETE | `/events` | Clear all events |

### Authentication

```
Authorization: Bearer vcp-demo-token-2026
```

## From Demo to Production

| Aspect | Demo | Production |
|--------|------|------------|
| Endpoint | `localhost:8765` | `https://api.veritaschain.org` |
| Token | `vcp-demo-token-2026` | Provided after NDA |
| Storage | In-memory | Distributed ledger |
| Anchoring | None | External timestamp |

**Ready for production?** Contact enterprise@veritaschain.org

---

**VeritasChain Standards Organization (VSO)**

*"Verify, Don't Trust"*
