import React, { useState } from 'react';
import { ChevronDown, ChevronUp, BookOpen, ShieldCheck } from 'lucide-react';

export function EvidencePanel({ sources = [], evidence = [] }) {
  const [isExpanded, setIsExpanded] = useState(false);

  // If there are no sources and no retrieved evidence, never render an empty panel
  const hasContent = (sources && sources.length > 0) || (evidence && evidence.length > 0);
  if (!hasContent) {
    return null;
  }

  const sourceCount = sources.length || evidence.length;

  return (
    <div className="evidence-section">
      <button
        type="button"
        className="evidence-toggle-btn"
        onClick={() => setIsExpanded((prev) => !prev)}
        aria-expanded={isExpanded}
        aria-label="Toggle supporting policy evidence"
      >
        <BookOpen size={14} />
        <span>View supporting sources ({sourceCount})</span>
        {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>

      {isExpanded && (
        <div className="evidence-panel-body">
          {/* Section ID Badges */}
          {sources.length > 0 && (
            <div>
              <div style={{ fontSize: '0.725rem', fontWeight: 600, color: 'var(--muted-slate)', marginBottom: '4px' }}>
                Cited Policy Sections:
              </div>
              <div className="cited-badges-row">
                {sources.map((sec, idx) => (
                  <span key={idx} className="source-badge">
                    [{sec}]
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Retrieved Grounding Details */}
          {evidence.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div style={{ fontSize: '0.725rem', fontWeight: 600, color: 'var(--muted-slate)' }}>
                Grounding Evidence Details:
              </div>
              {evidence.map((item, idx) => {
                const secId = item.section_id || 'General';
                const docName = item.source || 'Policy KB';
                const heading = item.heading || '';
                const effectiveFrom = item.effective_from;
                const status = item.status;
                const excerpt = item.excerpt;

                return (
                  <div key={idx} className="evidence-item-card">
                    <div className="evidence-item-head">
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span className="source-badge">[{secId}]</span>
                        <span className="evidence-heading">{heading}</span>
                      </div>
                      {status && (
                        <span style={{ fontSize: '0.675rem', color: '#0F766E', fontWeight: 600 }}>
                          {status}
                        </span>
                      )}
                    </div>

                    <div className="evidence-meta">
                      <span>Doc: <code>{docName}</code></span>
                      {effectiveFrom && <span> • Effective: <code>{effectiveFrom}</code></span>}
                    </div>

                    {excerpt && (
                      <div className="evidence-excerpt">
                        "{excerpt.length > 280 ? `${excerpt.slice(0, 280)}...` : excerpt}"
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default EvidencePanel;
