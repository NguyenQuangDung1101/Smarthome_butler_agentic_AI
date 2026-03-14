import React, { useState, useEffect, useRef, useCallback } from 'react';

const ChatTab = () => {
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [expandedEvents, setExpandedEvents] = useState({});
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  // ── Session list ──────────────────────────────────────────────────────────

  const fetchSessions = useCallback(async () => {
    try {
      const res = await fetch('/api/chat/sessions');
      if (!res.ok) return;
      const data = await res.json();
      setSessions(data);
    } catch (_) {}
  }, []);

  useEffect(() => {
    fetchSessions();
    const id = setInterval(fetchSessions, 5000);
    return () => clearInterval(id);
  }, [fetchSessions]);

  // ── Load existing session ─────────────────────────────────────────────────

  const loadSession = async (sessionId) => {
    if (isLoading) return;
    setActiveSessionId(sessionId);
    setMessages([]);
    setExpandedEvents({});
    try {
      const res = await fetch(`/api/chat/sessions/${encodeURIComponent(sessionId)}/messages`);
      if (!res.ok) return;
      const data = await res.json();
      if (Array.isArray(data)) setMessages(data);
    } catch (_) {}
    setTimeout(() => inputRef.current?.focus(), 50);
  };

  // ── New session ───────────────────────────────────────────────────────────

  const createNewSession = async () => {
    try {
      const res = await fetch('/api/chat/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      const data = await res.json();
      if (data.session_id) {
        const newEntry = { id: data.session_id, preview: 'New Chat', message_count: 0, is_running: false };
        setSessions(prev => [newEntry, ...prev]);
        setActiveSessionId(data.session_id);
        setMessages([]);
        setExpandedEvents({});
        setTimeout(() => inputRef.current?.focus(), 50);
      }
    } catch (_) {}
  };

  // ── Send message with SSE streaming ──────────────────────────────────────

  const sendMessage = async () => {
    const text = inputText.trim();
    if (!text || isLoading || !activeSessionId) return;

    setInputText('');
    setIsLoading(true);

    // Optimistically add user bubble
    const userEvent = { type: 'user', content: text, time: new Date().toLocaleString() };
    setMessages(prev => [...prev, userEvent]);

    try {
      const response = await fetch(
        `/api/chat/sessions/${encodeURIComponent(activeSessionId)}/message`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: text }),
        }
      );

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        setMessages(prev => [
          ...prev,
          { type: 'error', content: errData.error || `Server error ${response.status}`, time: new Date().toLocaleString() },
        ]);
        setIsLoading(false);
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const raw = line.slice(6).trim();
          if (!raw) continue;
          try {
            const event = JSON.parse(raw);
            if (event.type === 'done') {
              setIsLoading(false);
              fetchSessions();
              break;
            }
            // Skip user event — already shown optimistically
            if (event.type !== 'user') {
              setMessages(prev => [...prev, event]);
            }
          } catch (_) {}
        }
      }
    } catch (err) {
      setMessages(prev => [
        ...prev,
        { type: 'error', content: 'Connection error — check server.', time: new Date().toLocaleString() },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const toggleEvent = (idx) => {
    setExpandedEvents(prev => ({ ...prev, [idx]: prev[idx] === false ? true : false }));
  };

  // ── Render a single message event ─────────────────────────────────────────

  const renderMessage = (msg, idx) => {
    // Default collapsed state: tool_result and appliance start collapsed
    const isExpanded = expandedEvents[idx] !== false;

    if (msg.type === 'user') {
      return (
        <div key={idx} className="chat-msg-row chat-msg-user">
          <div className="chat-bubble chat-bubble-user">{msg.content}</div>
          <div className="chat-msg-time">{msg.time}</div>
        </div>
      );
    }

    if (msg.type === 'final') {
      return (
        <div key={idx} className="chat-msg-row chat-msg-agent">
          <div className="chat-role-badge">BEON AI</div>
          <div className="chat-bubble chat-bubble-final">{msg.content}</div>
          <div className="chat-msg-time">{msg.time}</div>
        </div>
      );
    }

    if (msg.type === 'tool_result') {
      const expanded = expandedEvents[idx] !== false; // default true
      return (
        <div key={idx} className="chat-msg-row chat-msg-agent">
          <div className="chat-event-card chat-event-tool">
            <div className="chat-event-header" onClick={() => toggleEvent(idx)}>
              <span className="chat-event-label">🔧 Tool · <span style={{ opacity: 0.8 }}>{msg.tool_name}</span></span>
              <span className="chat-event-toggle">{expanded ? '▲' : '▼'}</span>
            </div>
            {expanded && <div className="chat-event-body">{msg.content}</div>}
          </div>
          <div className="chat-msg-time">{msg.time}</div>
        </div>
      );
    }

    if (msg.type === 'appliance') {
      const expanded = expandedEvents[idx] !== false; // default true
      return (
        <div key={idx} className="chat-msg-row chat-msg-agent">
          <div className="chat-event-card chat-event-appliance">
            <div className="chat-event-header" onClick={() => toggleEvent(idx)}>
              <span className="chat-event-label">⚡ Appliance Execution</span>
              <span className="chat-event-toggle">{expanded ? '▲' : '▼'}</span>
            </div>
            {expanded && (
              <div className="chat-event-body">
                <div className="chat-event-sub-label">Config sent</div>
                <div style={{ marginBottom: 8 }}>{msg.appliance_config}</div>
                <div className="chat-event-sub-label">Result</div>
                <div>{msg.content}</div>
              </div>
            )}
          </div>
          <div className="chat-msg-time">{msg.time}</div>
        </div>
      );
    }

    if (msg.type === 'error') {
      return (
        <div key={idx} className="chat-msg-row chat-msg-agent">
          <div className="chat-event-card chat-event-error">
            ⚠️ {msg.content}
          </div>
        </div>
      );
    }

    return null;
  };

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="chat-layout">

      {/* ── Sidebar ── */}
      <div className="chat-sidebar">
        <button className="chat-new-btn" onClick={createNewSession}>＋ New Chat</button>
        <div className="chat-sessions-list">
          {sessions.length === 0 && (
            <div className="chat-sessions-empty">No sessions yet</div>
          )}
          {sessions.map(sess => (
            <div
              key={sess.id}
              className={`chat-session-item${sess.id === activeSessionId ? ' active' : ''}`}
              onClick={() => loadSession(sess.id)}
            >
              <div className="chat-session-preview">{sess.preview}</div>
              <div className="chat-session-time">{sess.id}</div>
              {sess.is_running && <div className="chat-session-running">● running</div>}
            </div>
          ))}
        </div>
      </div>

      {/* ── Main area ── */}
      <div className="chat-main">
        {!activeSessionId ? (
          <div className="chat-empty-state">
            <div style={{ fontSize: 48, marginBottom: 16 }}>🤖</div>
            <div>Select a chat or start a new one</div>
          </div>
        ) : (
          <>
            <div className="chat-messages">
              {messages.length === 0 && !isLoading && (
                <div className="chat-empty-state" style={{ paddingTop: 80 }}>
                  <div style={{ fontSize: 36, marginBottom: 12 }}>💬</div>
                  <div>Send a message to start chatting</div>
                </div>
              )}

              {messages.map((msg, idx) => renderMessage(msg, idx))}

              {isLoading && (
                <div className="chat-thinking">
                  <span className="chat-thinking-dots">AI is thinking</span>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            <div className="chat-input-bar">
              <input
                ref={inputRef}
                type="text"
                className="chat-input"
                value={inputText}
                onChange={e => setInputText(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage();
                  }
                }}
                placeholder="Message your home AI…"
                disabled={isLoading}
              />
              <button
                className="chat-send-btn"
                onClick={sendMessage}
                disabled={isLoading || !inputText.trim()}
              >
                {isLoading ? '…' : 'Send'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default ChatTab;
