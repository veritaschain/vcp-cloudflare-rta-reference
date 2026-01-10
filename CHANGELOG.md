# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-01-09

### Added

- **VCP v1.1 Full Compliance**
  - Policy Identification support (Section 5.5) - REQUIRED for all events
  - External Anchor preparation with Merkle tree buffer
  - `get_merkle_root()` method for batch anchoring
  - `clear_merkle_buffer()` method for post-anchor cleanup
  - `vcp_version: "1.1"` field in event headers

- **Sidecar Enhancements**
  - New initialization parameters: `policy_id`, `conformance_tier`, `issuer`, `use_hash_chain`
  - `_get_policy_identification()` internal method
  - `_add_to_merkle_buffer()` for RFC 6962 Merkle tree construction
  - Three-tier support constants: `TIER_SILVER`, `TIER_GOLD`, `TIER_PLATINUM`

- **Documentation**
  - Apache 2.0 LICENSE file
  - This CHANGELOG.md
  - Updated README with v1.1 compliance details
  - Policy Identification examples
  - External Anchor workflow documentation

### Changed

- **Hash Chain is now OPTIONAL** (per VCP v1.1 spec)
  - Controlled via `use_hash_chain` parameter (default: `True`)
  - `prev_hash` set to `None` when disabled
  - Recommended to keep enabled for local integrity

- **Event Structure**
  - All events now include `policy_identification` block
  - Header includes `vcp_version: "1.1"`
  - Security block handles optional `prev_hash`

- **Worker**
  - Added `X-VCP-Version: 1.1` header to requests

### Compliance Notes

VCP v1.1 introduces **certification-level** changes:

| Change | Protocol Impact | Certification Impact |
|--------|-----------------|---------------------|
| PrevHash → OPTIONAL | ✅ Compatible | No impact (relaxation) |
| External Anchor → REQUIRED | ✅ Compatible | ⚠️ All tiers must implement |
| Policy Identification → REQUIRED | ✅ Compatible | ⚠️ All events must include |

Existing v1.0 implementations remain **protocol-compatible** but may require updates for **v1.1 VC-Certified status**.

## [1.0.0] - 2026-01-09

### Added

- Initial release of VCP-Cloudflare PoC
- Cloudflare Worker for edge event ingestion
- Python Sidecar implementation
- Event types: SIG, ORD, EXE
- SHA-256 hash chain construction
- RFC 9562 UUID v7 generation
- RFC 8785 JSON canonicalization
- Demo runner with tamper detection
- Mock server for local testing
- Hash chain verifier tool

### Features

- VCP v1.0 Silver Tier compliance
- Trade lifecycle demonstration (SIG → ORD → EXE)
- Cryptographic hash chain linking
- Third-party verification capability
- NDA-gated production credentials

---

## Migration Guide: v1.0 → v1.1

### Sidecar Initialization

**v1.0:**
```python
sidecar = VCPSidecar(
    endpoint="...",
    api_key="...",
    venue_id="LMAX",
    account_id="acct:..."
)
```

**v1.1:**
```python
sidecar = VCPSidecar(
    endpoint="...",
    api_key="...",
    venue_id="LMAX",
    account_id="acct:...",
    # NEW: VCP v1.1 Policy Identification (REQUIRED)
    policy_id="com.yourcompany:trading-system-001",
    conformance_tier="SILVER",
    issuer="Your Company Name",
    use_hash_chain=True  # OPTIONAL in v1.1
)
```

### External Anchoring (NEW REQUIREMENT)

```python
# After generating events, compute Merkle root
merkle_root = sidecar.get_merkle_root()

# Submit to external anchor service (TSA, blockchain, etc.)
# Frequency: Silver=24h, Gold=1h, Platinum=10min

# After successful anchoring
sidecar.clear_merkle_buffer()
```

---

## Links

- [VCP v1.1 Specification](https://veritaschain.org/spec/v1.1)
- [VeritasChain GitHub](https://github.com/veritaschain)
- [Enterprise Contact](mailto:enterprise@veritaschain.org)
