import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Mic, Square, Send, Trash2, AlertCircle, RefreshCw } from 'lucide-react';
import { encodeWAV, resampleToMono16kHz } from '../utils/wavEncoder';

const MAX_RECORDING_SECONDS = 90;

export function VoiceRecorder({ onSendRecording, onCancel, disabled = false }) {
  const [recordState, setRecordState] = useState('idle'); // 'idle' | 'recording' | 'preview' | 'error'
  const [elapsedSec, setElapsedSec] = useState(0);
  const [audioBlob, setAudioBlob] = useState(null);
  const [audioUrl, setAudioUrl] = useState(null);
  const [errorMessage, setErrorMessage] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const mediaStreamRef = useRef(null);
  const audioContextRef = useRef(null);
  const processorNodeRef = useRef(null);
  const sourceNodeRef = useRef(null);
  const audioChunksRef = useRef([]);
  const timerRef = useRef(null);

  // Clean up streams and object URLs
  const cleanupAudio = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }

    if (processorNodeRef.current) {
      processorNodeRef.current.disconnect();
      processorNodeRef.current = null;
    }

    if (sourceNodeRef.current) {
      sourceNodeRef.current.disconnect();
      sourceNodeRef.current = null;
    }

    if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }

    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => {
      cleanupAudio();
      if (audioUrl) {
        URL.revokeObjectURL(audioUrl);
      }
    };
  }, [cleanupAudio, audioUrl]);

  /**
   * Start live microphone recording using Web Audio API.
   */
  const startRecording = async () => {
    setErrorMessage(null);
    setElapsedSec(0);
    audioChunksRef.current = [];

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setRecordState('error');
      setErrorMessage('Browser microphone access is not supported on this device/browser.');
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      mediaStreamRef.current = stream;

      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      const ctx = new AudioCtx();
      audioContextRef.current = ctx;

      const source = ctx.createMediaStreamSource(stream);
      sourceNodeRef.current = source;

      // Use ScriptProcessorNode to collect raw PCM samples
      const bufferSize = 4096;
      const processor = ctx.createScriptProcessor(bufferSize, 1, 1);
      processorNodeRef.current = processor;

      processor.onaudioprocess = (e) => {
        const inputData = e.inputBuffer.getChannelData(0);
        // Copy chunk
        audioChunksRef.current.push(new Float32Array(inputData));
      };

      source.connect(processor);
      processor.connect(ctx.destination);

      setRecordState('recording');

      // Start elapsed timer
      const startTime = Date.now();
      timerRef.current = setInterval(() => {
        const elapsed = Math.floor((Date.now() - startTime) / 1000);
        setElapsedSec(elapsed);

        if (elapsed >= MAX_RECORDING_SECONDS) {
          stopRecording();
        }
      }, 500);
    } catch (err) {
      cleanupAudio();
      setRecordState('error');
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        setErrorMessage('Microphone access was denied. Please allow microphone permissions in your browser address bar.');
      } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
        setErrorMessage('No microphone found on your system.');
      } else {
        setErrorMessage(`Microphone error: ${err.message}`);
      }
    }
  };

  /**
   * Stop recording and package samples into a 16kHz PCM WAV Blob.
   */
  const stopRecording = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }

    const ctx = audioContextRef.current;
    const stream = mediaStreamRef.current;

    // Collect all samples
    const chunks = audioChunksRef.current;
    const totalLength = chunks.reduce((acc, c) => acc + c.length, 0);

    if (totalLength === 0 || !ctx) {
      cleanupAudio();
      setRecordState('error');
      setErrorMessage('Recording was empty. Please speak clearly into your microphone.');
      return;
    }

    const fullBuffer = new Float32Array(totalLength);
    let offset = 0;
    for (const chunk of chunks) {
      fullBuffer.set(chunk, offset);
      offset += chunk.length;
    }

    // Resample from ctx.sampleRate to 16000 Hz if needed
    const sampleRate = ctx.sampleRate;
    let resampledSamples = fullBuffer;
    if (sampleRate !== 16000) {
      const ratio = sampleRate / 16000;
      const newLength = Math.round(totalLength / ratio);
      resampledSamples = new Float32Array(newLength);
      for (let i = 0; i < newLength; i++) {
        const originIdx = i * ratio;
        const lower = Math.floor(originIdx);
        const upper = Math.min(lower + 1, totalLength - 1);
        const weight = originIdx - lower;
        resampledSamples[i] = fullBuffer[lower] * (1 - weight) + fullBuffer[upper] * weight;
      }
    }

    // Clean up hardware tracks
    cleanupAudio();

    // Encode to standard 16-bit PCM WAV
    const wavBlob = encodeWAV(resampledSamples, 16000);
    const previewUrl = URL.createObjectURL(wavBlob);

    setAudioBlob(wavBlob);
    setAudioUrl(previewUrl);
    setRecordState('preview');
  };

  /**
   * Discard current recording and reset.
   */
  const discardRecording = () => {
    cleanupAudio();
    if (audioUrl) {
      URL.revokeObjectURL(audioUrl);
      setAudioUrl(null);
    }
    setAudioBlob(null);
    setRecordState('idle');
    setElapsedSec(0);
    setErrorMessage(null);
    if (onCancel) {
      onCancel();
    }
  };

  /**
   * Submit the recorded audio.
   */
  const handleSubmit = async () => {
    if (!audioBlob || isSubmitting) return;

    try {
      setIsSubmitting(true);
      await onSendRecording(audioBlob, 'Live Microphone Recording');
      discardRecording();
    } catch (err) {
      setErrorMessage(err.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="voice-recorder-overlay" role="region" aria-label="Live Voice Recorder">
      <div className="recorder-header">
        <div className="recorder-status">
          {recordState === 'recording' && <span className="recording-pulse" />}
          <span>
            {recordState === 'idle' && 'Click Start to record your voice inquiry'}
            {recordState === 'recording' && `Recording live: ${formatTime(elapsedSec)}`}
            {recordState === 'preview' && `Recording ready (${(audioBlob.size / 1024).toFixed(1)} KB)`}
            {recordState === 'error' && 'Recording failed'}
          </span>
        </div>
      </div>

      {/* Error message */}
      {errorMessage && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--accessible-red)', fontSize: '0.8rem' }}>
          <AlertCircle size={15} />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Audio Playback Preview */}
      {recordState === 'preview' && audioUrl && (
        <div style={{ width: '100%', margin: '4px 0' }}>
          <audio controls src={audioUrl} style={{ width: '100%', height: '36px' }}>
            Preview not supported
          </audio>
        </div>
      )}

      {/* Controls */}
      <div className="recorder-actions">
        {recordState === 'idle' && (
          <button
            type="button"
            className="btn-submit-voice"
            onClick={startRecording}
            disabled={disabled}
            aria-label="Start recording voice"
          >
            <Mic size={16} />
            <span>Start Speaking</span>
          </button>
        )}

        {recordState === 'recording' && (
          <button
            type="button"
            className="btn-record-stop"
            onClick={stopRecording}
            aria-label="Stop recording voice"
          >
            <Square size={16} />
            <span>Stop Recording</span>
          </button>
        )}

        {recordState === 'preview' && (
          <>
            <button
              type="button"
              className="btn-submit-voice"
              onClick={handleSubmit}
              disabled={isSubmitting || disabled}
              aria-label="Send recorded voice message"
            >
              <Send size={15} />
              <span>{isSubmitting ? 'Sending...' : 'Send Voice Message'}</span>
            </button>
            <button
              type="button"
              className="btn-discard-voice"
              onClick={discardRecording}
              disabled={isSubmitting}
              aria-label="Discard recording"
            >
              <Trash2 size={15} />
              <span>Discard</span>
            </button>
          </>
        )}

        {recordState === 'error' && (
          <button
            type="button"
            className="btn-discard-voice"
            onClick={startRecording}
            aria-label="Try recording again"
          >
            <RefreshCw size={15} />
            <span>Try Again</span>
          </button>
        )}
      </div>
    </div>
  );
}

export default VoiceRecorder;
