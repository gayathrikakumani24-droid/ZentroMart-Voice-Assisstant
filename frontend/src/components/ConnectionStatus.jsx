import React from 'react';
import { AlertCircle, WifiOff } from 'lucide-react';

export function ConnectionStatus({ connectionStatus = 'connecting', onRetry }) {
  if (connectionStatus === 'connected') {
    return null;
  }

  return (
    <div
      style={{
        backgroundColor: 'var(--accessible-red-bg)',
        borderBottom: '1px solid #FECDCA',
        color: 'var(--accessible-red)',
        padding: '8px 16px',
        fontSize: '0.825rem',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        zIndex: 25,
      }}
      role="alert"
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <WifiOff size={16} />
        <span>
          <b>Backend Disconnected:</b> Unable to reach ZentroMart backend service.
        </span>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          style={{
            background: 'none',
            border: 'none',
            color: 'var(--accessible-red)',
            fontWeight: 700,
            textDecoration: 'underline',
            cursor: 'pointer',
          }}
        >
          Retry Connection
        </button>
      )}
    </div>
  );
}

export default ConnectionStatus;
