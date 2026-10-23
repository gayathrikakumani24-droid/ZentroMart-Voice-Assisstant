import React, { useState, useRef, useEffect } from 'react';
import { Send, Mic, Paperclip } from 'lucide-react';
import VoiceRecorder from './VoiceRecorder';

export function ChatComposer({ onSendMessage, onSendVoiceRecording, isLoading = false }) {
  const [inputText, setInputText] = useState('');
  const [showVoiceRecorder, setShowVoiceRecorder] = useState(false);
  const textareaRef = useRef(null);

  // Auto-resize textarea height
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`;
    }
  }, [inputText]);

  const handleSend = () => {
    const trimmed = inputText.trim();
    if (!trimmed || isLoading) return;

    onSendMessage(trimmed);
    setInputText('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="composer-wrapper">
      <div className="composer-box">
        {/* Voice recorder expandable area */}
        {showVoiceRecorder && (
          <VoiceRecorder
            onSendRecording={async (blob, label) => {
              await onSendVoiceRecording(blob, label);
              setShowVoiceRecorder(false);
            }}
            onCancel={() => setShowVoiceRecorder(false)}
            disabled={isLoading}
          />
        )}

        {/* Text Input Row */}
        <div className="composer-input-row">
          <textarea
            ref={textareaRef}
            className="composer-textarea"
            placeholder="Type your question here (e.g. 'What is the return window for clothing?')..."
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
            rows={1}
            aria-label="Customer inquiry input"
          />

          <div className="composer-actions">
            {/* Toggle Microphone Recorder */}
            <button
              type="button"
              className={`btn-icon ${showVoiceRecorder ? 'active' : ''}`}
              onClick={() => setShowVoiceRecorder((prev) => !prev)}
              disabled={isLoading}
              title={showVoiceRecorder ? 'Close Voice Recorder' : 'Talk to ZentroMart (Live Mic)'}
              aria-label="Toggle voice recording"
            >
              <Mic size={19} />
            </button>

            {/* Send Button */}
            <button
              type="button"
              className="btn-icon btn-send"
              onClick={handleSend}
              disabled={isLoading || !inputText.trim()}
              title="Send message (Enter)"
              aria-label="Send message"
            >
              {isLoading ? (
                <div className="loading-indicator">
                  <span className="loading-dot" />
                  <span className="loading-dot" />
                  <span className="loading-dot" />
                </div>
              ) : (
                <Send size={17} />
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ChatComposer;
