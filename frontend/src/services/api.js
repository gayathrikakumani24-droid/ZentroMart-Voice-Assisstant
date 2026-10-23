/**
 * ZentroMart VoiceOps — API Client for React Frontend.
 *
 * Communicates with the FastAPI backend.
 * Zero credentials in browser; all Groq and Gnani calls are handled by the backend.
 */

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');

export class APIError extends Error {
  constructor(message, status = null) {
    super(message);
    this.name = 'APIError';
    this.status = status;
  }
}

/**
 * Perform a JSON request with robust error formatting.
 */
async function request(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  try {
    const res = await fetch(url, options);
    if (!res.ok) {
      let errorDetail = `Request failed with status ${res.status}`;
      try {
        const data = await res.json();
        if (data && data.detail) {
          errorDetail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
        }
      } catch {
        // Response was not JSON
      }
      throw new APIError(errorDetail, res.status);
    }
    return await res.json();
  } catch (err) {
    if (err instanceof APIError) {
      throw err;
    }
    throw new APIError(`Could not connect to ZentroMart backend service (${err.message}).`);
  }
}

export const api = {
  /**
   * Health check and service readiness.
   */
  async checkHealth() {
    return request('/health', { method: 'GET' });
  },

  /**
   * Create a new isolated conversation session.
   */
  async createSession() {
    const data = await request('/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    return data.session_id;
  },

  /**
   * Fetch metadata for a session.
   */
  async getSessionMetadata(sessionId) {
    return request(`/sessions/${encodeURIComponent(sessionId)}`, { method: 'GET' });
  },

  /**
   * Reset or clear an active session.
   */
  async resetSession(sessionId) {
    return request(`/sessions/${encodeURIComponent(sessionId)}`, { method: 'DELETE' });
  },

  /**
   * Send a multi-turn customer text message.
   */
  async sendChatMessage(message, sessionId = null) {
    const payload = { message: message.trim() };
    if (sessionId) {
      payload.session_id = sessionId;
    }

    return request('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },

  /**
   * Upload customer voice recording for STT -> Agent -> TTS.
   * Sends audio Blob as multipart/form-data.
   */
  async uploadVoiceMessage(audioBlob, sessionId = null, filename = 'recording.wav') {
    const formData = new FormData();
    formData.append('file', audioBlob, filename);
    if (sessionId) {
      formData.append('session_id', sessionId);
    }

    const url = `${API_BASE_URL}/voice`;
    try {
      const res = await fetch(url, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        let errorDetail = `Voice request failed (${res.status})`;
        try {
          const data = await res.json();
          if (data && data.detail) {
            errorDetail = data.detail;
          }
        } catch {
          // not json
        }
        throw new APIError(errorDetail, res.status);
      }

      return await res.json();
    } catch (err) {
      if (err instanceof APIError) {
        throw err;
      }
      throw new APIError(`Failed to process voice request: ${err.message}`);
    }
  },
};

export default api;
