import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import WelcomeState from '../components/WelcomeState';
import EvidencePanel from '../components/EvidencePanel';
import AudioReply from '../components/AudioReply';
import ChatMessage from '../components/ChatMessage';
import Sidebar from '../components/Sidebar';
import ChatComposer from '../components/ChatComposer';

describe('React Component Unit Tests', () => {
  // 1. WelcomeState
  it('renders welcome screen with 4 interactive suggestion cards', () => {
    const handleSelect = vi.fn();
    render(<WelcomeState onSelectSuggestion={handleSelect} />);

    expect(screen.getByText('How can we help you today?')).toBeInTheDocument();
    expect(screen.getByText('How long does a wallet refund take?')).toBeInTheDocument();
    expect(screen.getByText('What is the return window for electronics?')).toBeInTheDocument();
    expect(screen.getByText('How can I claim my product warranty?')).toBeInTheDocument();
    expect(screen.getByText('I need help with an existing order.')).toBeInTheDocument();

    // Click a suggestion card
    fireEvent.click(screen.getByText('How long does a wallet refund take?'));
    expect(handleSelect).toHaveBeenCalledWith('How long does a wallet refund take?');
  });

  // 2. EvidencePanel — Hidden by default and empty handling
  it('does NOT render evidence panel if sources and evidence are empty', () => {
    const { container } = render(<EvidencePanel sources={[]} evidence={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders evidence label collapsed by default and expands on click', () => {
    const sources = ['RET-9', 'REF-2'];
    const evidence = [
      {
        section_id: 'RET-9',
        source: '01_returns.md',
        heading: 'Clothing & Apparel',
        effective_from: '2026-08-01',
        excerpt: 'Apparel items are eligible for return within 15 days.',
      },
    ];

    render(<EvidencePanel sources={sources} evidence={evidence} />);

    // Clickable toggle button is visible with count
    const toggleBtn = screen.getByRole('button', { name: /toggle supporting policy evidence/i });
    expect(toggleBtn).toBeInTheDocument();
    expect(toggleBtn).toHaveAttribute('aria-expanded', 'false');

    // Details are NOT visible before clicking
    expect(screen.queryByText(/Clothing & Apparel/i)).not.toBeInTheDocument();

    // Click to expand
    fireEvent.click(toggleBtn);
    expect(toggleBtn).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByText('Clothing & Apparel')).toBeInTheDocument();
    expect(screen.getAllByText('[RET-9]').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('[REF-2]')).toBeInTheDocument();
    expect(screen.getByText(/Apparel items are eligible/i)).toBeInTheDocument();
  });

  // 3. AudioReply — Playback and TTS fallback
  it('renders audio element when audioBase64 is provided and ttsGenerated is true', () => {
    const { container } = render(
      <AudioReply audioBase64="UklGRg==" ttsGenerated={true} />
    );
    const audioEl = container.querySelector('audio');
    expect(audioEl).toBeInTheDocument();
    expect(audioEl.src).toContain('data:audio/wav;base64,UklGRg==');
  });

  it('displays fallback message when TTS synthesis fails', () => {
    render(<AudioReply audioBase64={null} ttsGenerated={false} ttsError="Credit exhausted" />);
    expect(screen.getByText(/Spoken audio playback is temporarily unavailable/i)).toBeInTheDocument();
  });

  // 4. ChatMessage — Customer vs Assistant rendering
  it('renders customer message with Soft Mint container and voice tag', () => {
    const userMsg = {
      id: '1',
      role: 'user',
      content: 'Can I exchange shoes?',
      isVoice: true,
      audioLabel: 'Live Microphone Recording',
      timestamp: '14:30',
    };
    render(<ChatMessage message={userMsg} />);

    expect(screen.getByText('Can I exchange shoes?')).toBeInTheDocument();
    expect(screen.getByText('Live Microphone Recording')).toBeInTheDocument();
    expect(screen.getByText('14:30')).toBeInTheDocument();
  });

  it('renders assistant message with answer, ticket notice, and evidence panel', () => {
    const asstMsg = {
      id: '2',
      role: 'assistant',
      content: 'Yes, shoes can be exchanged within 15 days.',
      sources: ['RET-9'],
      evidence: [{ section_id: 'RET-9', heading: 'Footwear' }],
      ticketCreated: true,
      ticketId: 'TCK-9901',
      timestamp: '14:31',
    };
    render(<ChatMessage message={asstMsg} />);

    expect(screen.getByText(/Yes, shoes can be exchanged/i)).toBeInTheDocument();
    expect(screen.getByText(/Escalation Ticket Confirmed:/i)).toBeInTheDocument();
    expect(screen.getByText('TCK-9901')).toBeInTheDocument();
    expect(screen.getByText(/View supporting sources/i)).toBeInTheDocument();
  });

  // 5. Sidebar
  it('renders Midnight Navy sidebar with connection status and new conversation button', () => {
    const handleNew = vi.fn();
    render(
      <Sidebar
        sessionId="sess_test_sidebar_123"
        turnCount={3}
        connectionStatus="connected"
        onNewConversation={handleNew}
      />
    );

    expect(screen.getByText('ZentroMart')).toBeInTheDocument();
    expect(screen.getByText('VoiceOps AI Support')).toBeInTheDocument();
    expect(screen.getByText(/Connected \(Port 8000\)/i)).toBeInTheDocument();
    expect(screen.getByText('sess_test_sidebar_123')).toBeInTheDocument();

    const newBtn = screen.getByRole('button', { name: /start new conversation/i });
    fireEvent.click(newBtn);
    expect(handleNew).toHaveBeenCalled();
  });

  // 6. ChatComposer — Enter to send and Shift+Enter for newline
  it('triggers onSendMessage on Enter and avoids sending on empty text', () => {
    const handleSend = vi.fn();
    render(<ChatComposer onSendMessage={handleSend} onSendVoiceRecording={vi.fn()} />);

    const textarea = screen.getByPlaceholderText(/Type your question here/i);
    const sendBtn = screen.getByRole('button', { name: /send message/i });

    // Disabled initially because textarea is empty
    expect(sendBtn).toBeDisabled();

    // Type query
    fireEvent.change(textarea, { target: { value: 'How fast are wallet refunds?' } });
    expect(sendBtn).not.toBeDisabled();

    // Press Shift+Enter: should NOT send
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: true });
    expect(handleSend).not.toHaveBeenCalled();

    // Press Enter: should send
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false });
    expect(handleSend).toHaveBeenCalledWith('How fast are wallet refunds?');
  });

  // 7. Verified order status display in multi-turn chat history
  it('renders verified order delivery status turn correctly without losing existing conversation turns', () => {
    const messages = [
      { id: '1', role: 'user', content: 'What is the status of my order 46637226?' },
      { id: '2', role: 'assistant', content: 'Please verify with your delivery pincode or phone last 4 digits.' },
      { id: '3', role: 'user', content: '122002' },
      { id: '4', role: 'assistant', content: 'Thank you. Your identity has been verified.' },
      { id: '5', role: 'user', content: 'What is the status of delivery?' },
      { id: '6', role: 'assistant', content: 'Your order #46637226 has been delivered on 12 October 2026.', orderStatus: 'delivered', isVerified: true },
    ];

    const { rerender } = render(
      <div>
        {messages.slice(0, 4).map((m) => (
          <ChatMessage key={m.id} message={m} />
        ))}
      </div>
    );

    expect(screen.getByText('What is the status of my order 46637226?')).toBeInTheDocument();
    expect(screen.getByText('122002')).toBeInTheDocument();

    // Rerender with subsequent delivery status turns (simulating message list updates)
    rerender(
      <div>
        {messages.map((m) => (
          <ChatMessage key={m.id} message={m} />
        ))}
      </div>
    );

    // Initial turns remain preserved
    expect(screen.getByText('What is the status of my order 46637226?')).toBeInTheDocument();
    expect(screen.getByText('What is the status of delivery?')).toBeInTheDocument();
    expect(screen.getByText('Your order #46637226 has been delivered on 12 October 2026.')).toBeInTheDocument();
  });
});
