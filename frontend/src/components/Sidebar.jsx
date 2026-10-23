import React from 'react';
import { ShoppingBag, PlusCircle, CheckCircle2, XCircle, RotateCcw, ShieldCheck, Clock, Mic, X } from 'lucide-react';

export function Sidebar({
  sessionId,
  turnCount = 0,
  connectionStatus = 'connecting',
  onNewConversation,
  isOpen = false,
  onClose,
  disabled = false,
}) {
  const isConnected = connectionStatus === 'connected';

  return (
    <aside className={`sidebar ${isOpen ? 'open' : ''}`} aria-label="Sidebar navigation">
      {/* Header */}
      <div className="sidebar-header">
        <div className="brand-icon-box" aria-hidden="true">
          🛍️
        </div>
        <div style={{ flex: 1 }}>
          <div className="brand-title">ZentroMart</div>
          <div className="brand-subtitle">VoiceOps AI Support</div>
        </div>
        {onClose && (
          <button
            className="btn-icon mobile-menu-toggle"
            onClick={onClose}
            aria-label="Close sidebar"
            style={{ color: '#94A3B8' }}
          >
            <X size={20} />
          </button>
        )}
      </div>

      {/* Content */}
      <div className="sidebar-content">
        <div className="sidebar-actions">
          <button
            className="btn-new-chat"
            onClick={onNewConversation}
            disabled={disabled}
            aria-label="Start new conversation"
          >
            <PlusCircle size={18} />
            <span>New Conversation</span>
          </button>
        </div>

        {/* Backend Connection Status */}
        <div className="sidebar-card">
          <div className="sidebar-card-title">Backend Status</div>
          <div
            className={`status-pill ${isConnected ? 'status-online' : 'status-offline'}`}
            role="status"
          >
            <span className="status-dot" aria-hidden="true" />
            <span>{isConnected ? 'Connected (Port 8000)' : 'Disconnected'}</span>
          </div>
        </div>

        {/* Active Session Info */}
        <div className="sidebar-card">
          <div className="sidebar-card-title">Active Session</div>
          {sessionId ? (
            <div>
              <div className="session-badge" title={sessionId}>
                {sessionId}
              </div>
              <div style={{ fontSize: '0.75rem', color: '#94A3B8', marginTop: '6px' }}>
                Completed Turns: <b style={{ color: '#F8FAFC' }}>{turnCount}</b>
              </div>
            </div>
          ) : (
            <div style={{ fontSize: '0.75rem', color: '#94A3B8' }}>No active session.</div>
          )}
        </div>

        {/* Support Capabilities Help */}
        <div className="sidebar-card" style={{ flex: 1 }}>
          <div className="sidebar-card-title">What I can help with</div>
          <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.785rem', color: '#CBD5E1' }}>
            <li style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <ShieldCheck size={14} color="#5EEAD4" />
              <span>Strict grounded returns & refund policies</span>
            </li>
            <li style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Clock size={14} color="#5EEAD4" />
              <span>Verified order tracking & delivery status</span>
            </li>
            <li style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Mic size={14} color="#5EEAD4" />
              <span>Live speech recognition & Kaveri voice</span>
            </li>
          </ul>
        </div>
      </div>

      {/* Footer */}
      <div className="sidebar-footer">
        <div>ZentroMart VoiceOps v1.0.0</div>
        <div style={{ fontSize: '0.7rem', color: '#64748B' }}>Powered by FastAPI & Gnani.ai</div>
      </div>
    </aside>
  );
}

export default Sidebar;
