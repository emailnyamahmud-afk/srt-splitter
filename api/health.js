// Health check endpoint for Edge TTS proxy.
// GET /api/health → returns JSON status, useful to verify deployment works.

export default function handler(req, res) {
  // CORS
  res.setHeader('Access-Control-Allow-Origin', '*')
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS')
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type')

  if (req.method === 'OPTIONS') {
    return res.status(200).end()
  }

  return res.status(200).json({
    status: 'ok',
    service: 'edge-tts-proxy',
    timestamp: new Date().toISOString(),
    endpoints: {
      tts: 'POST /api/edge-tts (body: { text, voice, rate, volume, pitch })',
      health: 'GET /api/health',
    },
    voices: [
      'id-ID-GadisNeural',
      'id-ID-ArdiNeural',
      'en-US-AriaNeural',
      'en-US-GuyNeural',
    ],
  })
}
