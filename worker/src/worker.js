/**
 * VCP Ingest Worker v1.0
 * Reference PoC for VCP event ingestion (non-certified).
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

function hasHeaderSecret(value) {
  // Reject absent/non-string values before interpolation into an HTTP header.
  // Visible ASCII also excludes empty, whitespace-only and CR/LF values.
  return typeof value === 'string' && /^[\x21-\x7e]+$/.test(value);
}

function hasRequiredConfiguration(env) {
  if (!hasHeaderSecret(env?.INGEST_TOKEN) || !hasHeaderSecret(env?.VCP_API_KEY)) {
    return false;
  }
  const target = env?.VCP_LOGGING_URL;
  if (typeof target !== 'string' || !target || target !== target.trim()
      || /[\x00-\x20\x7f]/.test(target)) {
    return false;
  }
  try {
    const url = new URL(target);
    return url.protocol === 'https:' && !url.username && !url.password && !url.hash;
  } catch {
    return false;
  }
}

function errorResponse(error, status) {
  return new Response(JSON.stringify({ error }), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

async function matchesAuthorization(header, token) {
  if (typeof header !== 'string') return false;
  const encode = (value) => new TextEncoder().encode(value);
  // Delegate the comparison to Web Crypto's HMAC verifier. Do not compare
  // secret-bearing strings or MAC bytes with JavaScript equality operators.
  // This preserves the existing exact Bearer header contract.
  const key = await crypto.subtle.importKey(
    'raw', encode(token), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign', 'verify'],
  );
  const expected = await crypto.subtle.sign('HMAC', key, encode(`Bearer ${token}`));
  return crypto.subtle.verify('HMAC', key, expected, encode(header));
}

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
      return errorResponse('Method not allowed', 405);
    }

    // A missing binding must never turn the literal "undefined" or "null"
    // into a usable bearer credential. Do not parse or forward until configured.
    if (!hasRequiredConfiguration(env)) {
      return errorResponse('Ingest service is not configured', 503);
    }

    const authHeader = request.headers.get('authorization');
    let authorized;
    try {
      authorized = await matchesAuthorization(authHeader, env.INGEST_TOKEN);
    } catch {
      // A cryptographic runtime failure is never an authorization fallback.
      return errorResponse('Authentication service unavailable', 503);
    }
    if (!authorized) {
      return errorResponse('Unauthorized', 401);
    }

    let event;
    try {
      event = await request.json();
    } catch (e) {
      return errorResponse('Invalid JSON', 400);
    }

    if (!event || typeof event !== 'object' || Array.isArray(event)
        || !event.header?.event_id || !event.header?.event_type_code) {
      return errorResponse('Missing required fields', 400);
    }

    event.edge_observation = generateEdgeMetadata(request);

    try {
      const vcpResponse = await fetch(env.VCP_LOGGING_URL, {
        method: 'POST',
        // Do not forward the configured API key through an upstream redirect.
        redirect: 'error',
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
