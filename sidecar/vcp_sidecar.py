#!/usr/bin/env python3
"""
VCP Sidecar Implementation v1.1
Production sidecar for VCP v1.1 compliant event generation and transmission.

Implements:
- VCP v1.1 Three-Layer Architecture
- Policy Identification (REQUIRED)
- External Anchor preparation (REQUIRED for all tiers)
- SHA-256 hash chain (OPTIONAL per v1.1)

Production Endpoint: ████████████████████████████████ (provided after NDA)

@copyright 2026 VeritasChain Standards Organization
@license Apache-2.0
"""

import json
import hashlib
import uuid
import time
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from typing import Dict, List, Optional


class VCPSidecar:
    """
    VCP Sidecar for generating and transmitting VCP v1.1 compliant events.
    
    VCP v1.1 Key Changes:
    - Policy Identification: REQUIRED for all events
    - External Anchor: REQUIRED for all tiers (Silver: 24h, Gold: 1h, Platinum: 10min)
    - PrevHash: OPTIONAL (local integrity mechanism)
    
    Production credentials are provided after NDA execution.
    Contact: enterprise@veritaschain.org
    """
    
    # VCP v1.1 Conformance Tiers
    TIER_SILVER = "SILVER"
    TIER_GOLD = "GOLD"
    TIER_PLATINUM = "PLATINUM"
    
    def __init__(
        self, 
        endpoint: str, 
        api_key: str, 
        venue_id: str, 
        account_id: str,
        policy_id: str = "org.veritaschain.demo:silver-default",
        conformance_tier: str = "SILVER",
        issuer: str = "VeritasChain Standards Organization",
        use_hash_chain: bool = True
    ):
        """
        Initialize VCP v1.1 Sidecar.
        
        Args:
            endpoint: VCP Ingest Worker URL (provided after NDA)
            api_key: Sidecar authentication token (provided after NDA)
            venue_id: Trading venue identifier (e.g., LMAX, SAXO)
            account_id: Your account identifier
            policy_id: Policy identifier (format: reverse_domain:local_id)
            conformance_tier: SILVER | GOLD | PLATINUM
            issuer: Organization operating the policy
            use_hash_chain: Enable hash chain linking (OPTIONAL in v1.1)
        """
        self.endpoint = endpoint
        self.api_key = api_key
        self.venue_id = venue_id
        self.account_id = account_id
        
        # VCP v1.1 Policy Identification
        self.policy_id = policy_id
        self.conformance_tier = conformance_tier
        self.issuer = issuer
        self.use_hash_chain = use_hash_chain
        
        # Hash chain state (OPTIONAL in v1.1, but recommended)
        self._prev_hash = "0" * 64 if use_hash_chain else None
        
        # Merkle tree buffer for anchoring
        self._merkle_buffer: List[str] = []
        self._policy_effective_date = int(time.time() * 1e9)
    
    def _generate_uuid_v7(self) -> str:
        """Generate RFC 9562 UUID v7"""
        timestamp_ms = int(time.time() * 1000)
        timestamp_hex = format(timestamp_ms, '012x')
        random_part = uuid.uuid4().hex
        return f"{timestamp_hex[:8]}-{timestamp_hex[8:12]}-7{random_part[:3]}-{format(0x80, '02x')}{random_part[3:6]}-{random_part[6:18]}"
    
    def _compute_hash(self, event: Dict) -> str:
        """Compute SHA-256 hash (RFC 8785 canonicalization)"""
        hashable = {"header": event["header"], "payload": event["payload"]}
        canonical = json.dumps(hashable, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical.encode()).hexdigest()
    
    def _get_policy_identification(self) -> Dict:
        """
        Generate VCP v1.1 Policy Identification block.
        
        Required for all VCP v1.1 events per Section 5.5.
        """
        return {
            "version": "1.1",
            "policy_id": self.policy_id,
            "conformance_tier": self.conformance_tier,
            "registration_policy": {
                "issuer": self.issuer,
                "policy_uri": f"https://veritaschain.org/policies/{self.policy_id}",
                "effective_date": self._policy_effective_date
            },
            "verification_depth": {
                "hash_chain_validation": self.use_hash_chain,
                "merkle_proof_required": True,  # Always true in v1.1
                "external_anchor_required": True  # Always true in v1.1
            }
        }
    
    def _add_to_merkle_buffer(self, event_hash: str):
        """Add event hash to Merkle tree buffer for anchoring."""
        self._merkle_buffer.append(event_hash)
    
    def get_merkle_root(self) -> Optional[str]:
        """
        Compute Merkle root from buffered event hashes.
        
        Call this before external anchoring (frequency per tier):
        - Silver: Every 24 hours
        - Gold: Every 1 hour
        - Platinum: Every 10 minutes
        """
        if not self._merkle_buffer:
            return None
        
        hashes = self._merkle_buffer.copy()
        while len(hashes) > 1:
            if len(hashes) % 2 == 1:
                hashes.append(hashes[-1])  # Duplicate last for odd count
            new_hashes = []
            for i in range(0, len(hashes), 2):
                combined = hashes[i] + hashes[i + 1]
                new_hashes.append(hashlib.sha256(combined.encode()).hexdigest())
            hashes = new_hashes
        return hashes[0]
    
    def clear_merkle_buffer(self):
        """Clear Merkle buffer after successful anchoring."""
        self._merkle_buffer = []
    
    def emit_signal(self, symbol: str, algo_id: str, 
                    algo_version: str = "1.0.0",
                    decision_factors: Optional[Dict] = None) -> str:
        """
        Emit a SIG (Signal) event.
        
        Args:
            symbol: Trading symbol (e.g., USDJPY)
            algo_id: Algorithm identifier
            algo_version: Algorithm version
            decision_factors: Decision metadata
            
        Returns:
            event_id (trace_id for subsequent events)
        """
        now = datetime.now(timezone.utc)
        event_id = self._generate_uuid_v7()
        
        event = {
            "header": {
                "event_id": event_id,
                "trace_id": event_id,
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
                "vcp_version": "1.1"  # VCP v1.1 version identifier
            },
            "payload": {
                "vcp_gov": {
                    "algo_id": algo_id,
                    "algo_version": algo_version,
                    "decision_factors": decision_factors or {}
                }
            },
            "policy_identification": self._get_policy_identification()  # VCP v1.1 REQUIRED
        }
        
        event_hash = self._compute_hash(event)
        event["security"] = {
            "event_hash": event_hash,
            "prev_hash": self._prev_hash if self.use_hash_chain else None
        }
        
        if self.use_hash_chain:
            self._prev_hash = event_hash
        
        self._add_to_merkle_buffer(event_hash)
        self._send(event)
        return event_id
    
    def emit_order(self, trace_id: str, symbol: str, order_id: str,
                   side: str, order_type: str, quantity: str, price: str,
                   time_in_force: str = "GTC") -> str:
        """Emit an ORD (Order) event"""
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
                    "time_in_force": time_in_force
                }
            },
            "policy_identification": self._get_policy_identification()
        }
        
        event_hash = self._compute_hash(event)
        event["security"] = {
            "event_hash": event_hash,
            "prev_hash": self._prev_hash if self.use_hash_chain else None
        }
        
        if self.use_hash_chain:
            self._prev_hash = event_hash
        
        self._add_to_merkle_buffer(event_hash)
        self._send(event)
        return event_id
    
    def emit_execution(self, trace_id: str, symbol: str, order_id: str,
                       exec_id: str, side: str, exec_price: str,
                       exec_quantity: str, commission: str = "0") -> str:
        """Emit an EXE (Execution) event"""
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
                    "commission": commission
                }
            },
            "policy_identification": self._get_policy_identification()
        }
        
        event_hash = self._compute_hash(event)
        event["security"] = {
            "event_hash": event_hash,
            "prev_hash": self._prev_hash if self.use_hash_chain else None
        }
        
        if self.use_hash_chain:
            self._prev_hash = event_hash
        
        self._add_to_merkle_buffer(event_hash)
        self._send(event)
        return event_id
    
    def _send(self, event: Dict):
        """Send event to VCP Ingest Worker"""
        data = json.dumps(event).encode()
        req = Request(
            self.endpoint,
            data=data,
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.api_key}',
                'X-VCP-Version': '1.1'
            }
        )
        with urlopen(req, timeout=10) as resp:
            return resp.status


# VCP v1.1 Usage example (credentials provided after NDA)
# 
# sidecar = VCPSidecar(
#     endpoint="████████████████████████████████",
#     api_key="████████████████████████████████",
#     venue_id="LMAX",
#     account_id="acct:████████████",
#     # VCP v1.1 Policy Identification (REQUIRED)
#     policy_id="com.example.trading:prod-algo-001",
#     conformance_tier="SILVER",
#     issuer="Example Trading Ltd",
#     use_hash_chain=True  # OPTIONAL in v1.1, but recommended
# )
#
# # Generate events
# trace_id = sidecar.emit_signal("USDJPY", "algo-001", decision_factors={"confidence": "0.85"})
# sidecar.emit_order(trace_id, "USDJPY", "ORD-001", "BUY", "LIMIT", "10000", "157.50")
# sidecar.emit_execution(trace_id, "USDJPY", "ORD-001", "EXE-001", "BUY", "157.48", "10000")
#
# # External Anchor (REQUIRED for all tiers in v1.1)
# merkle_root = sidecar.get_merkle_root()
# # Submit merkle_root to external anchor service (blockchain, TSA, etc.)
# # After successful anchoring:
# sidecar.clear_merkle_buffer()
