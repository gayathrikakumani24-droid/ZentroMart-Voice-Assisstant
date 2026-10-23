import React from 'react';
import { Mic, Ticket } from 'lucide-react';
import EvidencePanel from './EvidencePanel';
import AudioReply from './AudioReply';

export function ChatMessage({ message }) {
  const isUser = message.role === 'user';

  if (isUser) {
    return (
      <div className="message-row user" role="article" aria-label="Customer message">
        <div className="message-bubble">
          <div className="message-text">
            {message.content}
          </div>
          {message.isVoice && (
            <div className="user-audio-tag">
              <Mic size={13} />
              <span>{message.audioLabel || 'Voice Message'}</span>
            </div>
          )}
          {message.timestamp && (
            <div style={{ textAlign: 'right', fontSize: '0.675rem', color: '#065F46', marginTop: '4px' }}>
              {message.timestamp}
            </div>
          )}
        </div>
      </div>
    );
  }

  // Assistant Message
  return (
    <div className="message-row assistant" role="article" aria-label="Assistant response">
      <div className="message-bubble">
        {/* Header */}
        <div className="assistant-header">
          <div className="assistant-identity">
            <div className="avatar-badge" aria-hidden="true">
              🛍️
            </div>
            <span className="assistant-name">ZentroMart Support</span>
          </div>
          {message.timestamp && (
            <span className="message-timestamp">{message.timestamp}</span>
          )}
        </div>

        {/* Message Content */}
        <div className="message-text">
          {message.content.split('\n\n').map((paragraph, idx) => (
            <p key={idx}>{paragraph}</p>
          ))}
        </div>

        {/* Spoken Voice Playback */}
        {(message.audioBase64 || message.audioUrl || message.isVoice) && (
          <AudioReply
            audioBase64={message.audioBase64}
            audioUrl={message.audioUrl}
            ttsGenerated={message.ttsGenerated}
            ttsError={message.ttsError}
          />
        )}

        {/* Ticket Creation Badge */}
        {message.ticketCreated && message.ticketId && (
          <div className="ticket-badge">
            <Ticket size={15} />
            <span>Escalation Ticket Confirmed: <b>{message.ticketId}</b></span>
          </div>
        )}

        {/* Collapsible Policy Grounding Evidence */}
        <EvidencePanel
          sources={message.sources || []}
          evidence={message.evidence || []}
        />
      </div>
    </div>
  );
}

export default ChatMessage;
