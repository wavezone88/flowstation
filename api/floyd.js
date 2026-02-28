export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  if (req.method !== 'POST') {
    return res.status(405).json({ error: { message: 'Method not allowed' } });
  }

  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    return res.status(500).json({ error: { message: 'API key not configured on server.' } });
  }

  const body = req.body;
  if (!body || !body.messages || !Array.isArray(body.messages)) {
    return res.status(400).json({ error: { message: 'Invalid request: messages array required.' } });
  }

  const ALLOWED_MODELS = [
    'claude-sonnet-4-6',
    'claude-haiku-4-5-20251001',
    'claude-sonnet-4-20250514',
    'claude-haiku-4-5-20251001'
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
    const upstream = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': apiKey,
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify(payload),
    });

    const data = await upstream.json();
    return res.status(upstream.status).json(data);
  } catch (err) {
    return res.status(500).json({ error: { message: 'Upstream error. Please try again.' } });
  }
}
