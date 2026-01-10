/**
 * VCP Ingest Worker v1.0
 * Production implementation for VCP event ingestion.
 * 
 * Deployment: Cloudflare Workers
 * Endpoint: ████████████████████████████████ (provided after NDA)
 * 
 * @copyright 2026 VeritasChain Standards Organization
 * @license Apache-2.0
 */

const VALID_EVENT_TYPES = {
  'SIG': 1, 'ORD': 2, 'ACK': 3, 'REJ': 4,
  'EXE': 5, 'CXL': 6, 'MOD': 7,
};

function generateEdgeMetadata(request) {
  return {
    cf_ray: request.headers.get('cf-ray') || null,
    colo: request.cf?.colo || null,
    asn: request.cf?.asn || null,
    country: request.cf?.country || null,
    observed_at: new Date().toISOString()
  };
}

export default {
  async fetch(request, env, ctx) {
    if (request.method === 'OPTIONS') {
      return new Response(null, {
        headers: {
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Methods': 'POST, OPTIONS',
          'Access-Control-Allow-Headers': 'Content-Type, Authorization',
        }
      });
    }

    if (request.method !== 'POST') {
      return new Response(JSON.stringify({ error: 'Method not allowed' }), { status: 405 });
    }

    const authHeader = request.headers.get('authorization');
    if (authHeader !== `Bearer ${env.INGEST_TOKEN}`) {
      return new Response(JSON.stringify({ error: 'Unauthorized' }), { status: 401 });
    }

    let event;
    try {
      event = await request.json();
    } catch (e) {
      return new Response(JSON.stringify({ error: 'Invalid JSON' }), { status: 400 });
    }

    if (!event.header?.event_id || !event.header?.event_type_code) {
      return new Response(JSON.stringify({ error: 'Missing required fields' }), { status: 400 });
    }

    event.edge_observation = generateEdgeMetadata(request);

    try {
      const vcpResponse = await fetch(env.VCP_LOGGING_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': env.VCP_API_KEY,
          'X-VCP-Source': 'cloudflare-worker'
        },
        body: JSON.stringify(event)
      });

      return new Response(await vcpResponse.text(), {
        status: vcpResponse.status,
        headers: {
          'Content-Type': 'application/json',
          'X-VCP-Request-ID': event.header.event_id
        }
      });
    } catch (e) {
      return new Response(JSON.stringify({
        error: 'Gateway error',
        event_id: event.header?.event_id
      }), { status: 502 });
    }
  }
};
