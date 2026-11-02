import assert from 'node:assert/strict';
import { test } from 'node:test';
import worker from '../src/worker.js';

const CONFIG = {
  INGEST_TOKEN: 'synthetic-ingest-token',
  VCP_LOGGING_URL: 'https://logging.example.invalid/ingest',
  VCP_API_KEY: 'synthetic-upstream-key',
};
const EVENT = {
  header: { event_id: 'synthetic-event-1', event_type_code: 1 },
  payload: { synthetic: true },
  security: { event_hash: 'unverified-synthetic-value' },
};

function request(authorization = `Bearer ${CONFIG.INGEST_TOKEN}`, body = JSON.stringify(EVENT)) {
  const headers = { 'Content-Type': 'application/json' };
  if (authorization !== null) headers.Authorization = authorization;
  return new Request('https://worker.example.invalid/ingest', {
    method: 'POST', headers, body,
  });
}

function upstream(t, implementation = async () => new Response('{"accepted":true}', { status: 202 })) {
  const calls = [];
  t.mock.method(globalThis, 'fetch', async (...args) => {
    calls.push(args);
    return implementation(...args);
  });
  return calls;
}

for (const [label, token, header] of [
  ['missing token', undefined, 'Bearer undefined'],
  ['null token', null, 'Bearer null'],
  ['numeric token', 123, 'Bearer 123'],
  ['empty token', '', 'Bearer '],
  ['whitespace token', '   ', 'Bearer    '],
  ['padded token', ' synthetic-ingest-token ', 'Bearer synthetic-ingest-token'],
]) {
  test(`configuration fails closed: ${label}`, async (t) => {
    const calls = upstream(t);
    const config = { ...CONFIG, INGEST_TOKEN: token };
    if (token === undefined) delete config.INGEST_TOKEN;
    const response = await worker.fetch(request(header), config, {});
    assert.equal(response.status, 503);
    assert.deepEqual(await response.json(), { error: 'Ingest service is not configured' });
    assert.equal(calls.length, 0);
  });
}

for (const [key, value] of [
  ['VCP_API_KEY', undefined], ['VCP_API_KEY', null], ['VCP_API_KEY', ''],
  ['VCP_API_KEY', '   '], ['VCP_API_KEY', 'key\r\nInjected: value'],
  ['VCP_LOGGING_URL', undefined], ['VCP_LOGGING_URL', ''],
  ['VCP_LOGGING_URL', 'not-a-url'], ['VCP_LOGGING_URL', 'http://logging.example.invalid/ingest'],
  ['VCP_LOGGING_URL', 'https://user:password@logging.example.invalid/ingest'],
  ['VCP_LOGGING_URL', 'https://logging.example.invalid/ingest#fragment'],
]) {
  test(`configuration rejects ${key}=${JSON.stringify(value)}`, async (t) => {
    const calls = upstream(t);
    const response = await worker.fetch(request(), { ...CONFIG, [key]: value }, {});
    assert.equal(response.status, 503);
    assert.equal(calls.length, 0);
    assert.deepEqual(await response.json(), { error: 'Ingest service is not configured' });
  });
}

test('missing environment fails before parsing JSON or forwarding', async (t) => {
  const calls = upstream(t);
  const response = await worker.fetch(request('Bearer undefined', '{invalid'), undefined, {});
  assert.equal(response.status, 503);
  assert.equal(calls.length, 0);
});

for (const header of [null, 'Bearer incorrect', 'Bearer undefined', 'Basic synthetic-ingest-token',
  'Bearer synthetic-ingest-token-more', 'Bearer synthetic-ingest-token, Bearer incorrect',
  'Bearer xynthetic-ingest-token', 'Bearer synthetic-xngest-token', 'Bearer synthetic-ingest-tokex']) {
  test(`unauthorized request is not forwarded: ${JSON.stringify(header)}`, async (t) => {
    const calls = upstream(t);
    // Malformed JSON must not override the authentication failure.
    const response = await worker.fetch(request(header, '{invalid'), CONFIG, {});
    assert.equal(response.status, 401);
    assert.deepEqual(await response.json(), { error: 'Unauthorized' });
    assert.equal(calls.length, 0);
  });
}

test('cryptographic comparison failure does not parse or forward a request', async (t) => {
  const calls = upstream(t);
  t.mock.method(crypto.subtle, 'verify', async () => {
    throw new Error(`not public: ${CONFIG.INGEST_TOKEN}`);
  });
  const response = await worker.fetch(request(undefined, '{invalid'), CONFIG, {});
  assert.equal(response.status, 503);
  assert.deepEqual(await response.json(), { error: 'Authentication service unavailable' });
  assert.equal(calls.length, 0);
});

test('valid token forwards only the configured upstream credential and preserves the event', async (t) => {
  const calls = upstream(t);
  const input = request();
  const response = await worker.fetch(input, CONFIG, {});
  assert.equal(response.status, 202);
  assert.deepEqual(await response.json(), { accepted: true });
  assert.equal(response.headers.get('X-VCP-Request-ID'), EVENT.header.event_id);
  assert.equal(calls.length, 1);
  const [url, options] = calls[0];
  assert.equal(url, CONFIG.VCP_LOGGING_URL);
  assert.equal(options.method, 'POST');
  assert.equal(options.redirect, 'error');
  assert.equal(options.headers['X-API-Key'], CONFIG.VCP_API_KEY);
  assert.equal(options.headers.Authorization, undefined);
  const forwarded = JSON.parse(options.body);
  assert.deepEqual(forwarded.header, EVENT.header);
  assert.deepEqual(forwarded.payload, EVENT.payload);
  assert.deepEqual(forwarded.security, EVENT.security);
  assert.ok(Number.isFinite(Date.parse(forwarded.edge_observation.observed_at)));
});

for (const body of ['not-json', 'null', '[]', '"string"', '{}', '{"header":null}']) {
  test(`malformed event does not reach upstream: ${body}`, async (t) => {
    const calls = upstream(t);
    const response = await worker.fetch(request(undefined, body), CONFIG, {});
    assert.equal(response.status, 400);
    assert.equal(calls.length, 0);
  });
}

test('upstream failure returns a gateway error without exposing credentials', async (t) => {
  const calls = upstream(t, async () => { throw new Error(`not public: ${CONFIG.VCP_API_KEY}`); });
  const response = await worker.fetch(request(), CONFIG, {});
  assert.equal(response.status, 502);
  assert.equal(calls.length, 1);
  assert.deepEqual(await response.json(), { error: 'Gateway error', event_id: EVENT.header.event_id });
});

test('OPTIONS remains a non-mutating preflight without authentication', async (t) => {
  const calls = upstream(t);
  const response = await worker.fetch(new Request('https://worker.example.invalid/', { method: 'OPTIONS' }), {}, {});
  assert.equal(response.status, 200);
  assert.equal(calls.length, 0);
});

test('unsupported method never reaches upstream', async (t) => {
  const calls = upstream(t);
  const response = await worker.fetch(new Request('https://worker.example.invalid/'), CONFIG, {});
  assert.equal(response.status, 405);
  assert.equal(calls.length, 0);
});
