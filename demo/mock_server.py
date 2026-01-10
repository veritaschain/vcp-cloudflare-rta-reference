#!/usr/bin/env python3
"""
VCP Mock Ingest Server v1.0
Local mock server for PoC demonstration.

This server simulates the production VCP Ingest Worker endpoint,
allowing users to test the full VCP flow without NDA credentials.

@copyright 2026 VeritasChain Standards Organization
@license Apache-2.0
"""

import json
import hashlib
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timezone
from typing import Dict, List
import threading
import os

# In-memory storage for received events
received_events: List[Dict] = []
event_lock = threading.Lock()

# Demo token (for local testing only)
DEMO_TOKEN = "vcp-demo-token-2026"


class VCPMockHandler(BaseHTTPRequestHandler):
    """Mock handler simulating VCP Ingest Worker behavior."""
    
    def log_message(self, format, *args):
        """Custom log format."""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]}")
    
    def _send_json(self, status: int, data: Dict):
        """Send JSON response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()
    
    def do_GET(self):
        """Handle GET requests."""
        if self.path == '/health':
            self._send_json(200, {
                "status": "healthy",
                "mode": "demo",
                "version": "1.0.0",
                "events_received": len(received_events)
            })
        elif self.path == '/events':
            with event_lock:
                self._send_json(200, {
                    "count": len(received_events),
                    "events": received_events
                })
        elif self.path == '/events/export':
            with event_lock:
                # Export as JSONL for verifier
                self.send_response(200)
                self.send_header('Content-Type', 'application/x-ndjson')
                self.send_header('Content-Disposition', 'attachment; filename="vcp_events.jsonl"')
                self.end_headers()
                for event in received_events:
                    self.wfile.write((json.dumps(event) + '\n').encode())
        elif self.path == '/':
            self._send_json(200, {
                "service": "VCP Mock Ingest Server",
                "version": "1.0.0",
                "mode": "DEMO (Local Only)",
                "endpoints": {
                    "POST /ingest": "Submit VCP events",
                    "GET /events": "List received events",
                    "GET /events/export": "Export events as JSONL",
                    "GET /health": "Health check",
                    "DELETE /events": "Clear all events"
                },
                "note": "This is a local demo server. Production endpoints require NDA."
            })
        else:
            self._send_json(404, {"error": "Not found"})
    
    def do_POST(self):
        """Handle POST requests (event ingestion)."""
        if self.path != '/ingest':
            self._send_json(404, {"error": "Not found"})
            return
        
        # Check authorization
        auth = self.headers.get('Authorization', '')
        if auth != f'Bearer {DEMO_TOKEN}':
            self._send_json(401, {
                "error": "Unauthorized",
                "hint": "Use token: vcp-demo-token-2026"
            })
            return
        
        # Parse event
        content_length = int(self.headers.get('Content-Length', 0))
        try:
            body = self.rfile.read(content_length)
            event = json.loads(body)
        except json.JSONDecodeError:
            self._send_json(400, {"error": "Invalid JSON"})
            return
        
        # Validate required fields
        if not event.get('header', {}).get('event_id'):
            self._send_json(400, {"error": "Missing header.event_id"})
            return
        
        if not event.get('header', {}).get('event_type'):
            self._send_json(400, {"error": "Missing header.event_type"})
            return
        
        # Add server-side metadata
        event['_server'] = {
            "received_at": datetime.now(timezone.utc).isoformat(),
            "sequence": len(received_events) + 1,
            "mode": "demo"
        }
        
        # Store event
        with event_lock:
            received_events.append(event)
        
        event_type = event['header']['event_type']
        event_id = event['header']['event_id'][:8]
        
        self._send_json(200, {
            "status": "accepted",
            "event_id": event['header']['event_id'],
            "sequence": event['_server']['sequence'],
            "message": f"Event {event_type} ({event_id}...) ingested successfully"
        })
    
    def do_DELETE(self):
        """Handle DELETE requests."""
        if self.path == '/events':
            with event_lock:
                count = len(received_events)
                received_events.clear()
            self._send_json(200, {
                "status": "cleared",
                "events_deleted": count
            })
        else:
            self._send_json(404, {"error": "Not found"})


def run_server(port: int = 8765):
    """Start the mock server."""
    server = HTTPServer(('127.0.0.1', port), VCPMockHandler)
    
    print("=" * 60)
    print("VCP Mock Ingest Server")
    print("=" * 60)
    print()
    print(f"  Endpoint:  http://127.0.0.1:{port}")
    print(f"  Token:     {DEMO_TOKEN}")
    print()
    print("  This is a LOCAL DEMO server.")
    print("  Production endpoints require NDA execution.")
    print()
    print("=" * 60)
    print()
    print("Waiting for events... (Ctrl+C to stop)")
    print()
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    run_server(port)
