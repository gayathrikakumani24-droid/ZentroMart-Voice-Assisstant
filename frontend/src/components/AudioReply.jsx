import React from 'react';
import { Volume2, VolumeX } from 'lucide-react';

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');

export function AudioReply({ audioBase64, audioUrl, ttsGenerated = true, ttsError = null }) {
  // If voice synthesis succeeded, render playable HTML audio element
  if (ttsGenerated && (audioBase64 || audioUrl)) {
    const audioSrc = audioBase64
      ? `data:audio/wav;base64,${audioBase64}`
      : `${API_BASE_URL}${audioUrl}`;

    return (
      <div className="audio-reply-box">
        <div className="audio-reply-label">
          <Volume2 size={15} />
          <span>Spoken Audio Response (Kaveri voice)</span>
        </div>
        <audio controls src={audioSrc} preload="metadata">
          Your browser does not support the audio playback element.
        </audio>
      </div>
    );
  }

  // If TTS synthesis failed or is unavailable, show friendly message
  if (ttsError || !ttsGenerated) {
    return (
      <div className="audio-reply-unavailable">
        <VolumeX size={14} />
        <span>Spoken audio playback is temporarily unavailable.</span>
      </div>
    );
  }

  return null;
}

export default AudioReply;
