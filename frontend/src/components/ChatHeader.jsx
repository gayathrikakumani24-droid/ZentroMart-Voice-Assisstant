import React from 'react';
import { Menu, PlusCircle } from 'lucide-react';

export function ChatHeader({
  connectionStatus = 'connecting',
  onToggleSidebar,
  onNewConversation,
  disabled = false,
}) {
  const isConnected = connectionStatus === 'connected';

  return (
    <header className="chat-header">
      <div className="header-left">
        <button
          className="mobile-menu-toggle"
          onClick={onToggleSidebar}
          aria-label="Open sidebar menu"
        >
          <Menu size={22} />
        </button>
        <div className="header-title-wrap">
          <h1>AI Support Assistant</h1>
          <p>Your personal ZentroMart shopping support.</p>
        </div>
      </div>

      <div className="header-right">
        <div
          className={`status-pill ${isConnected ? 'status-online' : 'status-offline'}`}
          title={isConnected ? 'Connected to FastAPI backend' : 'Backend unreachable'}
        >
          <span className="status-dot" aria-hidden="true" />
          <span>{isConnected ? 'Online' : 'Offline'}</span>
        </div>

        <button
          className="btn-new-chat"
          style={{ width: 'auto', padding: '6px 12px', fontSize: '0.8rem' }}
          onClick={onNewConversation}
          disabled={disabled}
          title="Start fresh conversation"
        >
          <PlusCircle size={15} />
          <span>New Chat</span>
        </button>
      </div>
    </header>
  );
}

export default ChatHeader;
