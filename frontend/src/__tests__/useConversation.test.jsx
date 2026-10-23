import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import useConversation from '../hooks/useConversation';
import api from '../services/api';

vi.mock('../services/api');

describe('useConversation Hook Integration Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.checkHealth.mockResolvedValue({ status: 'healthy', service: 'zentromart-voiceops-api' });
    api.createSession.mockResolvedValue('sess_hook_test_1');
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('initializes session and connectionStatus on mount', async () => {
    const { result } = renderHook(() => useConversation());

    // Wait for initSession
    await act(async () => {
      await Promise.resolve();
    });

    expect(result.current.sessionId).toBe('sess_hook_test_1');
    expect(result.current.connectionStatus).toBe('connected');
    expect(result.current.messages).toEqual([]);
  });

  it('sends text query and appends both user and assistant turns', async () => {
    api.sendChatMessage.mockResolvedValueOnce({
      session_id: 'sess_hook_test_1',
      turn: 1,
      answer: 'Instant wallet refund in 2 hours.',
      decision: 'answer',
      sources: ['REF-2'],
      evidence: [{ section_id: 'REF-2', heading: 'Wallets' }],
      ticket_created: false,
    });

    const { result } = renderHook(() => useConversation());
    await act(async () => {
      await Promise.resolve();
    });

    await act(async () => {
      await result.current.sendMessage('How fast are refunds?');
    });

    expect(result.current.messages.length).toBe(2);
    expect(result.current.messages[0].role).toBe('user');
    expect(result.current.messages[0].content).toBe('How fast are refunds?');
    expect(result.current.messages[1].role).toBe('assistant');
    expect(result.current.messages[1].content).toBe('Instant wallet refund in 2 hours.');
    expect(result.current.messages[1].sources).toContain('REF-2');
  });

  it('resets conversation with fresh isolated backend session and clears messages', async () => {
    api.resetSession.mockResolvedValueOnce({ status: 'reset' });
    api.createSession
      .mockResolvedValueOnce('sess_hook_test_1')
      .mockResolvedValueOnce('sess_hook_test_2');

    const { result } = renderHook(() => useConversation());
    await act(async () => {
      await Promise.resolve();
    });
    expect(result.current.sessionId).toBe('sess_hook_test_1');

    // Send a message first
    api.sendChatMessage.mockResolvedValueOnce({ answer: 'Hello' });
    await act(async () => {
      await result.current.sendMessage('Hi');
    });
    expect(result.current.messages.length).toBe(2);

    // Now reset
    await act(async () => {
      await result.current.resetConversation();
    });

    expect(api.resetSession).toHaveBeenCalledWith('sess_hook_test_1');
    expect(result.current.sessionId).toBe('sess_hook_test_2');
    expect(result.current.messages).toEqual([]);
  });

  it('processes voice recording and prevents duplicate submission of same recording', async () => {
    api.uploadVoiceMessage.mockResolvedValueOnce({
      session_id: 'sess_hook_test_1',
      turn: 1,
      transcript: 'Track my order 89782837',
      answer: 'Please verify the last 4 digits of your phone number.',
      decision: 'clarify',
      tts_generated: true,
      audio_base64: 'UklGRg==',
    });

    const { result } = renderHook(() => useConversation());
    await act(async () => {
      await Promise.resolve();
    });

    const audioBlob = new Blob(['wav-voice-data'], { type: 'audio/wav' });

    // First voice submission
    await act(async () => {
      await result.current.sendVoiceRecording(audioBlob);
    });

    expect(result.current.messages.length).toBe(2);
    expect(result.current.messages[0].content).toBe('Track my order 89782837');
    expect(result.current.messages[0].isVoice).toBe(true);
    expect(result.current.messages[1].ttsGenerated).toBe(true);
    expect(api.uploadVoiceMessage).toHaveBeenCalledTimes(1);

    // Attempt to submit identical audioBlob again (duplicate prevention)
    await act(async () => {
      await result.current.sendVoiceRecording(audioBlob);
    });

    expect(result.current.error).toContain('already been submitted');
    expect(api.uploadVoiceMessage).toHaveBeenCalledTimes(1);
  });
});
