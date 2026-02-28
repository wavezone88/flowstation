import crypto from 'crypto';

const ALLOWED_ORIGINS = [
  'https://www.myflowstation.com',
  'https://myflowstation.com',
  'https://flowstation.vercel.app',
];

// ── In-memory IP rate limit (60 requests per IP per hour) ──────────────────
// Resets on cold start, but provides strong real-time throttling.
const ipBucket = new Map(); // ip → { count, resetAt }
const IP_LIMIT = 60;
const IP_WINDOW_MS = 60 * 60 * 1000; // 1 hour

function checkIpLimit(ip) {
  const now = Date.now();
  let bucket = ipBucket.get(ip);
  if (!bucket || now > bucket.resetAt) {
    bucket = { count: 0, resetAt: now + IP_WINDOW_MS };
    ipBucket.set(ip, bucket);
  }
  bucket.count++;
  return bucket.count <= IP_LIMIT;
}

// ── Anthropic call with model fallback ─────────────────────────────────────
async function callAnthropic(apiKey, payload) {
  const makeRequest = async (model) => {
    const body = { ...payload, model };
    const resp = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': apiKey,
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify(body),
    });
    return resp;
  };

  const FALLBACK_MODEL = 'claude-haiku-4-5-20251001';
  const primaryModel = payload.model;

  let resp = await makeRequest(primaryModel);

  // On quota / overload errors, retry with the cheaper haiku model
  if (
    resp.status === 429 || resp.status === 529 || resp.status === 402 ||
    (resp.status >= 500 && resp.status !== 500)
  ) {
    if (primaryModel !== FALLBACK_MODEL) {
      resp = await makeRequest(FALLBACK_MODEL);
    }
  }

  return resp;
}

export default async function handler(req, res) {
  const origin = req.headers.origin || '';
  const allowedOrigin = ALLOWED_ORIGINS.includes(origin) ? origin : ALLOWED_ORIGINS[0];

  res.setHeader('Access-Control-Allow-Origin', allowedOrigin);
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, X-Floyd-Token');
  res.setHeader('Vary', 'Origin');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  if (req.method !== 'POST') {
    return res.status(405).json({ error: { message: 'Method not allowed' } });
  }

  // ── CORS origin check ───────────────────────────────────────────────────
  if (!ALLOWED_ORIGINS.includes(origin)) {
    return res.status(403).json({ error: { message: 'Forbidden' } });
  }

  // ── Client token check ─────────────────────────────────────────────────
  const clientSecret = process.env.FLOYD_CLIENT_SECRET;
  if (clientSecret) {
    const provided = req.headers['x-floyd-token'] || '';
    const a = Buffer.from(provided.padEnd(clientSecret.length).slice(0, clientSecret.length));
    const b = Buffer.from(clientSecret);
    if (!crypto.timingSafeEqual(a, b) || provided.length !== clientSecret.length) {
      return res.status(401).json({ error: { message: 'Unauthorized' } });
    }
  }

  // ── IP rate limit ───────────────────────────────────────────────────────
  const ip =
    req.headers['x-real-ip'] ||
    req.headers['x-forwarded-for']?.split(',').pop()?.trim() ||
    req.socket?.remoteAddress ||
    'unknown';

  if (!checkIpLimit(ip)) {
    return res.status(429).json({
      error: { message: 'Rate limit reached. Please slow down and try again in an hour.' },
    });
  }

  // ── API key ─────────────────────────────────────────────────────────────
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    return res.status(500).json({ error: { message: 'API key not configured on server.' } });
  }

  // ── Validate body ───────────────────────────────────────────────────────
  const body = req.body;
  if (!body || !body.messages || !Array.isArray(body.messages)) {
    return res.status(400).json({ error: { message: 'Invalid request: messages array required.' } });
  }

  const ALLOWED_MODELS = [
    'claude-sonnet-4-6',
    'claude-haiku-4-5-20251001',
    'claude-sonnet-4-20250514',
  ];
  const model = ALLOWED_MODELS.includes(body.model) ? body.model : 'claude-haiku-4-5-20251001';
  const max_tokens = Math.min(Math.max(parseInt(body.max_tokens) || 600, 100), 2000);

  const payload = {
    model,
    max_tokens,
    messages: body.messages.slice(-20),
  };
  if (body.system && typeof body.system === 'string') {
    payload.system = body.system.slice(0, 5000);
  }

  try {
    const upstream = await callAnthropic(apiKey, payload);
    const data = await upstream.json();
    return res.status(upstream.status).json(data);
  } catch (err) {
    return res.status(500).json({ error: { message: 'Upstream error. Please try again.' } });
  }
}
