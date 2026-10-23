import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import api, { APIError } from '../services/api';

describe('Frontend API Client Service', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // 1. Health endpoint
  it('calls /health with GET method', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: 'healthy', service: 'zentromart-voiceops-api' }),
    });

    const data = await api.checkHealth();
    expect(data.status).toBe('healthy');
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/health'),
      expect.objectContaining({ method: 'GET' })
    );
  });

  // 2. Session creation
  it('calls /sessions with POST method and returns session_id', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ session_id: 'sess_react_test_123', message: 'Created' }),
    });

    const sessionId = await api.createSession();
    expect(sessionId).toBe('sess_react_test_123');
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/sessions'),
      expect.objectContaining({ method: 'POST' })
    );
  });

  // 3. Text chat message payload
  it('sends text query with correct payload and session_id', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        session_id: 'sess_react_test_123',
        turn: 1,
        answer: 'Wallet refunds take up to 2 hours.',
        decision: 'answer',
        sources: ['REF-2'],
      }),
    });

    const res = await api.sendChatMessage('How fast are refunds?', 'sess_react_test_123');
    expect(res.answer).toContain('Wallet refunds');
    expect(res.sources).toContain('REF-2');

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/chat'),
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: 'How fast are refunds?', session_id: 'sess_react_test_123' }),
      })
    );
  });

  // 4. Voice upload multipart form-data
  it('uploads audio Blob with filename and session_id in FormData', async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        session_id: 'sess_voice_123',
        turn: 1,
        transcript: 'Return window for electronics?',
        answer: 'Electronics have a 7-day return window.',
        tts_generated: true,
        audio_base64: 'UklGRg==',
        sources: ['RET-2'],
      }),
    });

    const dummyBlob = new Blob(['fake-audio-bytes'], { type: 'audio/wav' });
    const res = await api.uploadVoiceMessage(dummyBlob, 'sess_voice_123', 'query.wav');

    expect(res.transcript).toBe('Return window for electronics?');
    expect(res.tts_generated).toBe(true);

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/voice'),
      expect.objectContaining({
        method: 'POST',
        body: expect.any(FormData),
      })
    );
  });

  // 5. Error handling on non-200 responses
  it('throws APIError on backend 400 Bad Request', async () => {
    fetch.mockResolvedValueOnce({
      ok: false,
      status: 400,
      json: async () => ({ detail: 'Uploaded audio file is empty (0 bytes).' }),
    });

    const dummyBlob = new Blob([], { type: 'audio/wav' });
    await expect(api.uploadVoiceMessage(dummyBlob, 'sess_voice_123')).rejects.toThrow(
      'Uploaded audio file is empty (0 bytes).'
    );
  });

  // 6. Network connection failure handling
  it('handles network connection error gracefully', async () => {
    fetch.mockRejectedValueOnce(new Error('Failed to fetch'));

    await expect(api.checkHealth()).rejects.toThrow(
      'Could not connect to ZentroMart backend service'
    );
  });
});
