import { useState, useEffect, useCallback, useRef } from 'react';
import api, { APIError } from '../services/api';

export function useConversation() {
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState('connecting');
  const [healthInfo, setHealthInfo] = useState(null);
  const [error, setError] = useState(null);

  // Track submitted audio hashes to prevent duplicate submissions
  const submittedAudioHashes = useRef(new Set());
  const isSubmitting = useRef(false);

  // Initialize or restore session
  const initSession = useCallback(async () => {
    try {
      setConnectionStatus('connecting');
      const health = await api.checkHealth();
      setHealthInfo(health);
      if (health.status === 'healthy') {
        setConnectionStatus('connected');
      } else {
        setConnectionStatus('disconnected');
      }

      const newId = await api.createSession();
      setSessionId(newId);
      submittedAudioHashes.current.clear();
      return newId;
    } catch (err) {
      setConnectionStatus('disconnected');
      setError('Could not connect to ZentroMart support service. Please check your network.');
      return null;
    }
  }, []);

  useEffect(() => {
    initSession();
  }, [initSession]);

  // Periodic health check
  useEffect(() => {
    const timer = setInterval(async () => {
      try {
        const health = await api.checkHealth();
        setHealthInfo(health);
        setConnectionStatus(health.status === 'healthy' ? 'connected' : 'disconnected');
      } catch {
        setConnectionStatus('disconnected');
      }
    }, 15000);
    return () => clearInterval(timer);
  }, []);

  // Format current time
  const getTimestamp = () => {
    const now = new Date();
    return now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  /**
   * Send a text message to the assistant.
   */
  const sendMessage = useCallback(async (text) => {
    const cleanText = (text || '').trim();
    if (!cleanText || isSubmitting.current) return;

    isSubmitting.current = true;
    setIsLoading(true);
    setError(null);

    let activeSession = sessionId;
    if (!activeSession) {
      activeSession = await initSession();
      if (!activeSession) {
        setIsLoading(false);
        isSubmitting.current = false;
        return;
      }
    }

    // Add user turn immediately to UI
    const userMessageId = `user_${Date.now()}`;
    const userTurn = {
      id: userMessageId,
      role: 'user',
      content: cleanText,
      timestamp: getTimestamp(),
    };

    setMessages((prev) => [...prev, userTurn]);

    try {
      const res = await api.sendChatMessage(cleanText, activeSession);

      const assistantTurn = {
        id: `asst_${Date.now()}`,
        role: 'assistant',
        content: res.answer || '',
        decision: res.decision,
        sources: res.sources || [],
        evidence: res.evidence || [],
        ticketCreated: Boolean(res.ticket_created),
        ticketId: res.ticket_id,
        isVerified: res.is_verified,
        orderId: res.order_id,
        orderStatus: res.order_status,
        timestamp: getTimestamp(),
      };

      setMessages((prev) => [...prev, assistantTurn]);
    } catch (err) {
      const errorTurn = {
        id: `err_${Date.now()}`,
        role: 'assistant',
        content: `⚠️ **Unable to complete request:** ${err.message}`,
        timestamp: getTimestamp(),
        isError: true,
      };
      setMessages((prev) => [...prev, errorTurn]);
      setError(err.message);
    } finally {
      setIsLoading(false);
      isSubmitting.current = false;
    }
  }, [sessionId, initSession]);

  /**
   * Upload and process a voice message.
   */
  const sendVoiceRecording = useCallback(async (audioBlob, audioLabel = 'Live Microphone Recording') => {
    if (!audioBlob || isSubmitting.current) return;

    // Compute simple signature from byte length and type
    const audioSig = `${audioBlob.size}_${audioBlob.type}`;
    if (submittedAudioHashes.current.has(audioSig)) {
      setError('This recording has already been submitted.');
      return;
    }
    submittedAudioHashes.current.add(audioSig);

    isSubmitting.current = true;
    setIsLoading(true);
    setError(null);

    let activeSession = sessionId;
    if (!activeSession) {
      activeSession = await initSession();
      if (!activeSession) {
        setIsLoading(false);
        isSubmitting.current = false;
        return;
      }
    }

    try {
      const filename = `recording_${Date.now()}.wav`;
      const res = await api.uploadVoiceMessage(audioBlob, activeSession, filename);

      const transcript = (res.transcript || '').trim();

      // Add user spoken message
      const userTurn = {
        id: `user_voice_${Date.now()}`,
        role: 'user',
        content: transcript || '(Voice message)',
        isVoice: true,
        audioLabel,
        timestamp: getTimestamp(),
      };

      // Add assistant response with audio reply
      const assistantTurn = {
        id: `asst_voice_${Date.now()}`,
        role: 'assistant',
        content: res.answer || '',
        decision: res.decision,
        sources: res.sources || [],
        evidence: res.evidence || [],
        audioBase64: res.audio_base64,
        audioUrl: res.audio_url,
        ttsGenerated: Boolean(res.tts_generated),
        ttsError: res.error,
        isVoice: true,
        isVerified: res.is_verified,
        orderId: res.order_id,
        orderStatus: res.order_status,
        timestamp: getTimestamp(),
      };

      setMessages((prev) => [...prev, userTurn, assistantTurn]);
    } catch (err) {
      submittedAudioHashes.current.delete(audioSig); // allow retry on error
      const errorTurn = {
        id: `err_voice_${Date.now()}`,
        role: 'assistant',
        content: `⚠️ **Voice Processing Error:** ${err.message}`,
        timestamp: getTimestamp(),
        isError: true,
      };
      setMessages((prev) => [...prev, errorTurn]);
      setError(err.message);
    } finally {
      setIsLoading(false);
      isSubmitting.current = false;
    }
  }, [sessionId, initSession]);

  /**
   * Start a new conversation and isolate state.
   */
  const resetConversation = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    if (sessionId) {
      try {
        await api.resetSession(sessionId);
      } catch {
        // Safe to ignore on reset
      }
    }

    try {
      const newId = await api.createSession();
      setSessionId(newId);
      setMessages([]);
      submittedAudioHashes.current.clear();
    } catch (err) {
      setError(`Failed to reset session: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  }, [sessionId]);

  return {
    sessionId,
    messages,
    isLoading,
    connectionStatus,
    healthInfo,
    error,
    sendMessage,
    sendVoiceRecording,
    resetConversation,
    clearError: () => setError(null),
  };
}

export default useConversation;
