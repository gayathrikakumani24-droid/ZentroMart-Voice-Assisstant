import React from 'react';
import { CreditCard, RotateCcw, ShieldCheck, Package } from 'lucide-react';

const SUGGESTIONS = [
  {
    category: 'Refunds',
    icon: CreditCard,
    prompt: 'How long does a wallet refund take?',
  },
  {
    category: 'Returns',
    icon: RotateCcw,
    prompt: 'What is the return window for electronics?',
  },
  {
    category: 'Warranty',
    icon: ShieldCheck,
    prompt: 'How can I claim my product warranty?',
  },
  {
    category: 'Order Support',
    icon: Package,
    prompt: 'I need help with an existing order.',
  },
];

export function WelcomeState({ onSelectSuggestion, disabled = false }) {
  return (
    <div className="welcome-container" role="region" aria-label="Welcome screen">
      <div className="welcome-badge">
        🛍️ VoiceOps AI Desk
      </div>
      <h2 className="welcome-heading">How can we help you today?</h2>
      <p className="welcome-subtext">
        Ask about orders, returns, refunds, deliveries, or product warranties.
      </p>

      <div className="suggestions-grid">
        {SUGGESTIONS.map((item, idx) => {
          const Icon = item.icon;
          return (
            <button
              key={idx}
              type="button"
              className="suggestion-card"
              onClick={() => onSelectSuggestion(item.prompt)}
              disabled={disabled}
              aria-label={`Ask: ${item.prompt}`}
            >
              <div className="suggestion-category">
                <Icon size={14} />
                <span>{item.category}</span>
              </div>
              <div className="suggestion-query">{item.prompt}</div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default WelcomeState;
