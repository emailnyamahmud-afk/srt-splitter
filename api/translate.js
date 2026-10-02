// Vercel Serverless Function: Translation Proxy
//
// Google Translate unofficial API (gratis, no API key).
// Support: English (en), Indonesian (id), Javanese (jv), dll.
//
// POST /api/translate
// Body: { "text": "Hello world", "from": "en", "to": "id" }
// Response: { "translated": "Halo dunia" }

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed, use POST' });
  }

  const { text, from, to } = req.body || {};

  if (!text || typeof text !== 'string') {
    return res.status(400).json({ error: 'Field "text" is required' });
  }

  if (!to || typeof to !== 'string') {
    return res.status(400).json({ error: 'Field "to" (target language) is required' });
  }

  const sourceLang = from || 'auto';

  try {
    // Google Translate unofficial API
    // sl=auto untuk auto-detect, tl=target language
    const url = `https://translate.googleapis.com/translate_a/single?client=gtx&sl=${sourceLang}&tl=${to}&dt=t&q=${encodeURIComponent(text)}`;

    const response = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
      },
    });

    if (!response.ok) {
      return res.status(502).json({ error: `Google Translate error: HTTP ${response.status}` });
    }

    const data = await response.json();

    // Response format: [[[translatedText, originalText, ...], ...], ...]
    // data[0] = array of translation segments
    // data[0][i][0] = translated text segment
    let translated = '';
    if (data && data[0]) {
      for (const segment of data[0]) {
        if (segment && segment[0]) {
          translated += segment[0];
        }
      }
    }

    if (!translated) {
      return res.status(502).json({ error: 'Google Translate returned empty result' });
    }

    // Detected source language (data[2])
    const detectedLang = data[2] || sourceLang;

    return res.status(200).json({
      translated,
      detectedFrom: detectedLang,
    });
  } catch (e) {
    console.error('Translate error:', e.message);
    return res.status(502).json({ error: 'Translation failed: ' + e.message });
  }
}
