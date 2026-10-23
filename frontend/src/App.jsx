import React, { useState, useRef, useEffect } from 'react';
import useConversation from './hooks/useConversation';
import Sidebar from './components/Sidebar';
import ChatHeader from './components/ChatHeader';
import ChatMessage from './components/ChatMessage';
import WelcomeState from './components/WelcomeState';
import ChatComposer from './components/ChatComposer';
import ConnectionStatus from './components/ConnectionStatus';

export function App() {
  const {
    sessionId,
    messages,
    isLoading,
    connectionStatus,
    sendMessage,
    sendVoiceRecording,
    resetConversation,
  } = useConversation();

  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const messagesEndRef = useRef(null);

  // Auto-scroll to bottom of messages viewport on updates
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isLoading]);

  const userTurnsCount = messages.filter((m) => m.role === 'user').length;

  return (
    <div className="app-container">
      {/* Midnight Navy Sidebar */}
      <Sidebar
        sessionId={sessionId}
        turnCount={userTurnsCount}
        connectionStatus={connectionStatus}
        onNewConversation={() => {
          resetConversation();
          setIsSidebarOpen(false);
        }}
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
        disabled={isLoading}
      />

      {/* Main Chat Workspace */}
      <main className="chat-workspace">
        {/* Offline notification banner if backend is disconnected */}
        <ConnectionStatus
          connectionStatus={connectionStatus}
          onRetry={resetConversation}
        />

        {/* Top Header */}
        <ChatHeader
          connectionStatus={connectionStatus}
          onToggleSidebar={() => setIsSidebarOpen((prev) => !prev)}
          onNewConversation={resetConversation}
          disabled={isLoading}
        />

        {/* Messages Viewport */}
        <div className="messages-viewport" role="log" aria-live="polite">
          {messages.length === 0 ? (
            <WelcomeState
              onSelectSuggestion={sendMessage}
              disabled={isLoading}
            />
          ) : (
            messages.map((msg) => <ChatMessage key={msg.id} message={msg} />
            )
          )}

          {/* Assistant Typing Indicator */}
          {isLoading && (
            <div className="message-row assistant" aria-label="Assistant is reasoning">
              <div className="message-bubble" style={{ display: 'inline-flex', padding: '12px 18px', gap: '8px', alignItems: 'center' }}>
                <div className="avatar-badge" aria-hidden="true">
                  🛍️
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--muted-slate)', fontSize: '0.85rem' }}>
                  <span>Consulting ZentroMart policies</span>
                  <div className="loading-indicator">
                    <span className="loading-dot" />
                    <span className="loading-dot" />
                    <span className="loading-dot" />
                  </div>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Bottom Chat Composer with Live Microphone Recording */}
        <ChatComposer
          onSendMessage={sendMessage}
          onSendVoiceRecording={sendVoiceRecording}
          isLoading={isLoading}
        />
      </main>
    </div>
  );
}

export default App;
