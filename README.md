> **Status correction — 25 October 2026**
>
> - This is first-party proof-of-concept code by VeritasChain Co., Ltd., which operates the VeritasChain Standards Organization (VSO). It targets VCP v1.1 (Silver tier). VCP v1.1 has no tagged release and is superseded by VCP v1.2 (Released, tag `v1.2.0`).
> - Conformance to any VCP tier, or to VAP, has not been independently established. There are zero external implementations of VAP or any of its profiles, including VCP.
> - Not certified. VSO does not issue certifications itself. The certification scheme requires a Conformity Assessment Body (CAB) independent of the scheme owner; the only registered CAB, VeritasChain Co., Ltd., is not independent (VAP v1.2 ERRATA E-2026-10-21).
> - Known limitations: external anchoring is not implemented. The sidecar only computes a Merkle root (`get_merkle_root()`); submission to a TSA or blockchain is left as a comment, and the worker does no anchoring. The Merkle construction hashes concatenated hex strings with plain SHA-256 and duplicates the last node at odd levels; it is not RFC 6962 (no `0x00`/`0x01` domain separation). Events carry no signatures. The demo `event_id` values do not match the UUID format (the fourth group has five hex digits).
> - Whether an NDA-gated "production" service exists is not shown by anything in this repository. Mentions of production endpoints and credentials below describe an access model, not a verified deployment.

# VCP-Cloudflare Reference PoC

**Cloudflare Workers x VCP v1.1 Sidecar Integration**

[![VCP Version](https://img.shields.io/badge/VCP-v1.1-blue)](https://veritaschain.org)
[![License](https://img.shields.io/badge/License-Apache%202.0-green)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Non--certified_PoC-orange)](#)

> "Verify, Don't Trust" - Third-party verifiable audit trails for algorithmic trading systems.

## Overview

Proof-of-concept implementation of the **VeritasChain Protocol (VCP) v1.1** using Cloudflare Workers as an edge gateway. It targets **VCP v1.1 Silver Tier**; conformance has not been established. It includes:

- **Policy Identification** (REQUIRED in v1.1)
- **External Anchor preparation** (REQUIRED for all tiers)
- **Hash chain linking** (OPTIONAL, enabled by default)
- **Merkle tree construction** for batch anchoring

## VCP v1.1 Design Targets (not conformance results)

| v1.1 Requirement | Status | Notes |
|------------------|--------|-------|
| Policy Identification | Implemented (not assessed) | Section 5.5 |
| External Anchor | NOT IMPLEMENTED (Merkle root only) | 24h for Silver tier |
| Merkle Tree | Implemented, not RFC 6962 | No domain separation; odd-node duplication |
| Hash Chain | OPTIONAL | Enabled by default |
| Three-Layer Architecture | Partial (no external anchor) | Section 6 |

## Quick Start (Demo)

**Try VCP v1.1 locally without NDA credentials:**

```bash
cd demo
python run_demo.py
```

This demonstrates:
- VCP v1.1 event generation (SIG → ORD → EXE)
- Policy Identification in every event
- Cryptographic hash chain construction
- Merkle tree for external anchoring
- Tamper detection capability
- Third-party verification

## Repository Structure

```
vcp-cloudflare/
├── README.md
├── LICENSE                    # Apache 2.0
├── CHANGELOG.md               # Version history
├── demo/                      # ← Start here!
│   ├── run_demo.py            # One-command demo
│   ├── mock_server.py         # Local mock server
│   └── README.md              # Demo documentation
├── worker/
│   ├── src/worker.js          # Cloudflare Worker
│   └── wrangler.toml          # Deployment config
├── sidecar/
│   └── vcp_sidecar.py         # Python Sidecar (v1.1)
└── tools/
    └── vcp_verifier.py        # Hash chain verifier
```

## Access Levels

| Level | Contents | Access |
|-------|----------|--------|
| **Public** | Source code, documentation | GitHub (this repository) |
| **NDA Required** | API endpoints, credentials | Contact VSO |

## VCP v1.1 Key Features

### Policy Identification (NEW in v1.1)

Every event includes a `policy_identification` block:

```json
{
  "policy_identification": {
    "version": "1.1",
    "policy_id": "com.example.trading:prod-algo-001",
    "conformance_tier": "SILVER",
    "registration_policy": {
      "issuer": "Example Trading Ltd",
      "policy_uri": "https://veritaschain.org/policies/...",
      "effective_date": 1736438400000000000
    },
    "verification_depth": {
      "hash_chain_validation": true,
      "merkle_proof_required": true,
      "external_anchor_required": true
    }
  }
}
```

### External Anchor (REQUIRED for all tiers)

| Tier | Anchor Frequency | Method |
|------|------------------|--------|
| Silver | Every 24 hours | Merkle Root to TSA/Blockchain |
| Gold | Every 1 hour | Merkle Root to TSA/Blockchain |
| Platinum | Every 10 minutes | Merkle Root to TSA/Blockchain |

```python
# Get Merkle root for anchoring
merkle_root = sidecar.get_merkle_root()

# Submit to external anchor service
# ... (TSA, Ethereum, etc.)

# Clear buffer after successful anchor
sidecar.clear_merkle_buffer()
```

## Deployment

### 1. Deploy Cloudflare Worker

```bash
cd worker
wrangler login
wrangler secret put INGEST_TOKEN
wrangler secret put VCP_LOGGING_URL    # Provided after NDA
wrangler secret put VCP_API_KEY        # Provided after NDA
wrangler publish
```

### 2. Configure Sidecar (v1.1)

```python
from vcp_sidecar import VCPSidecar

sidecar = VCPSidecar(
    endpoint="███████████████████████████████",   # Provided after NDA
    api_key="███████████████████████████████",    # Provided after NDA
    venue_id="LMAX",                               # Your venue
    account_id="acct:███████████",                 # Your account
    # VCP v1.1 Policy Identification (REQUIRED)
    policy_id="com.yourcompany:trading-system-001",
    conformance_tier="SILVER",
    issuer="Your Company Name",
    use_hash_chain=True                            # OPTIONAL in v1.1
)
```

## Obtaining Production Credentials

Production API endpoints and credentials are provided after executing a Non-Disclosure Agreement (NDA) with VeritasChain Standards Organization.

**Contact**: enterprise@veritaschain.org

### NDA Package Contents

After NDA execution, you will receive:

| Item | Description |
|------|-------------|
| `VCP_LOGGING_URL` | Production API endpoint |
| `VCP_API_KEY` | Your organization's API key |
| `INGEST_TOKEN` | Sidecar authentication token |
| Worker domain | Your dedicated ingest endpoint |
| Policy ID | Your registered policy identifier |

## Conformance Status

| Requirement | Status |
|-------------|--------|
| VCP v1.1 Schema | Not assessed |
| Policy Identification | Implemented (not assessed) |
| External Anchoring | Not implemented |
| Silver Tier | Not established |

## Security

- All credentials are provided via secure channel after NDA
- API keys are rotated every 90 days
- TLS 1.3 required for all connections
- No credentials are stored in this repository
- Event signatures are not implemented in this PoC (Ed25519 is the VCP default algorithm)

## Standards Referenced

This implementation refers to the following. Conformance has not been assessed; the Merkle construction does not follow RFC 6962, and canonicalization uses Python `json.dumps(sort_keys=True)` rather than a full RFC 8785 implementation:

- **VCP v1.1 Specification** (2025-12-30)
- **RFC 9562**: UUID v7
- **RFC 8785**: JSON Canonicalization Scheme
- **RFC 6962**: Certificate Transparency (Merkle Trees)
- **RFC 3161**: Time-Stamp Protocol

## Contact

- **Enterprise Sales**: enterprise@veritaschain.org
- **Technical Support**: technical@veritaschain.org
- **Standards Inquiries**: standards@veritaschain.org
- **Website**: https://veritaschain.org
- **GitHub**: https://github.com/veritaschain

---

**VeritasChain Standards Organization (VSO)**

*"Verify, Don't Trust"*

---

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.
