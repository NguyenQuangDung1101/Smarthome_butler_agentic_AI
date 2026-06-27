import React, { useState, useEffect, useRef, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const ChatTab = () => {
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [expandedEvents, setExpandedEvents] = useState({});
  const [voiceActive, setVoiceActive] = useState(false);
  const [voiceState, setVoiceState] = useState('idle');
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const voicePollRef = useRef(null);
  const mediaStreamRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioContextRef = useRef(null);
  const analyserRef = useRef(null);
  const voiceFrameRef = useRef(null);
  const voiceRequestRef = useRef(null);
  const playbackSourceRef = useRef(null);
  const voiceActiveRef = useRef(false);
  const voiceSessionRef = useRef(null);
  const voicePhaseRef = useRef('idle');
  const messagesRef = useRef([]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    messagesRef.current = messages;
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

  // ── Voice polling ─────────────────────────────────────────────────────────

  useEffect(() => {
    if (!voiceActive || !activeSessionId) {
      clearInterval(voicePollRef.current);
      return;
    }

    voicePollRef.current = setInterval(async () => {
      if (voicePhaseRef.current !== 'processing') return;
      try {
        const [statusRes, messagesRes] = await Promise.all([
          fetch(`/api/voice/status/${encodeURIComponent(activeSessionId)}`),
          fetch(`/api/chat/sessions/${encodeURIComponent(activeSessionId)}/messages`),
        ]);
        const status = await statusRes.json();
        const eventLog = await messagesRes.json();

        // Ignore a polling response that finished after audio playback started.
        if (voicePhaseRef.current !== 'processing') return;

        if (!status.active) {
          await stopVoice(activeSessionId);
          return;
        }

        if (Array.isArray(eventLog)) {
          messagesRef.current = eventLog;
          setMessages(eventLog);
        }

        if (
          ['transcribing', 'agent_wait', 'processing'].includes(status.state)
        ) {
          setVoiceState(status.state);
        }
      } catch (_) {}
    }, 300);

    return () => clearInterval(voicePollRef.current);
  }, [voiceActive, activeSessionId]);

  // ── Voice toggle ──────────────────────────────────────────────────────────

  const chooseRecorderMimeType = () => {
    const types = [
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/mp4',
      'audio/ogg;codecs=opus',
    ];
    return types.find(type => MediaRecorder.isTypeSupported(type)) || '';
  };

  const cleanupVoice = () => {
    if (voiceFrameRef.current) {
      cancelAnimationFrame(voiceFrameRef.current);
      voiceFrameRef.current = null;
    }

    if (voiceRequestRef.current) {
      voiceRequestRef.current.abort();
      voiceRequestRef.current = null;
    }

    const recorder = mediaRecorderRef.current;
    mediaRecorderRef.current = null;
    if (recorder && recorder.state !== 'inactive') {
      recorder.onstop = null;
      recorder.stop();
    }

    if (playbackSourceRef.current) {
      try { playbackSourceRef.current.stop(); } catch (_) {}
      playbackSourceRef.current = null;
    }

    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach(track => track.stop());
      mediaStreamRef.current = null;
    }

    if (audioContextRef.current) {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }

    analyserRef.current = null;
  };

  const stopVoice = async (sessionId = voiceSessionRef.current || activeSessionId) => {
    voiceActiveRef.current = false;
    voiceSessionRef.current = null;
    voicePhaseRef.current = 'idle';
    cleanupVoice();
    setVoiceActive(false);
    setVoiceState('idle');

    if (sessionId) {
      await fetch('/api/voice/stop', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId }),
      }).catch(() => {});
    }
  };

  const playResponse = async (audioBase64) => {
    const audioContext = audioContextRef.current;
    if (!audioContext || !audioBase64) return;

    const binary = atob(audioBase64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) {
      bytes[i] = binary.charCodeAt(i);
    }

    const audioBuffer = await audioContext.decodeAudioData(bytes.buffer);
    await new Promise(resolve => {
      const source = audioContext.createBufferSource();
      playbackSourceRef.current = source;
      source.buffer = audioBuffer;
      source.connect(audioContext.destination);
      source.onended = () => {
        if (playbackSourceRef.current === source) playbackSourceRef.current = null;
        resolve();
      };
      voicePhaseRef.current = 'speaking';
      setVoiceState('speaking');
      source.start();
    });
  };

  const refreshVoiceMessages = async (sessionId) => {
    try {
      const res = await fetch(`/api/chat/sessions/${encodeURIComponent(sessionId)}/messages`);
      const data = await res.json();
      if (Array.isArray(data)) {
        messagesRef.current = data;
        setMessages(data);
      }
      fetchSessions();
    } catch (_) {}
  };

  const processVoice = async (sessionId, audioBlob) => {
    if (!voiceActiveRef.current || voiceSessionRef.current !== sessionId) return;

    voicePhaseRef.current = 'processing';
    setVoiceState('transcribing');

    const controller = new AbortController();
    voiceRequestRef.current = controller;
    const formData = new FormData();
    formData.append('session_id', sessionId);
    const extension = audioBlob.type.includes('mp4') ? 'm4a'
      : audioBlob.type.includes('ogg') ? 'ogg'
        : 'webm';
    formData.append('audio', audioBlob, `voice.${extension}`);

    try {
      const res = await fetch('/api/voice/process', {
        method: 'POST',
        body: formData,
        signal: controller.signal,
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error || 'Voice processing failed');
      }

      await refreshVoiceMessages(sessionId);
      if (!voiceActiveRef.current || voiceSessionRef.current !== sessionId) return;

      if (data.audio_base64) {
        await playResponse(data.audio_base64);
      }

      if (!voiceActiveRef.current || voiceSessionRef.current !== sessionId) return;

      await fetch('/api/voice/ready', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId }),
      }).catch(() => {});

      voicePhaseRef.current = 'capture';
      setVoiceState('speech_wait');
      startRecordingCycle(sessionId);
    } catch (error) {
      if (error.name === 'AbortError') return;
      alert(error.message || 'Voice processing failed');
      await stopVoice(sessionId);
    } finally {
      if (voiceRequestRef.current === controller) voiceRequestRef.current = null;
    }
  };

  const startRecordingCycle = (sessionId) => {
    const stream = mediaStreamRef.current;
    const analyser = analyserRef.current;
    if (!voiceActiveRef.current || !stream || !analyser) return;

    const mimeType = chooseRecorderMimeType();
    const recorder = mimeType
      ? new MediaRecorder(stream, { mimeType })
      : new MediaRecorder(stream);
    mediaRecorderRef.current = recorder;

    const analyserData = new Uint8Array(analyser.fftSize);
    const recordedChunks = [];
    const cycleStartedAt = performance.now();
    let speechDetected = false;
    let speechCandidateAt = 0;
    let speechStartedAt = 0;
    let silenceStartedAt = 0;

    recorder.ondataavailable = event => {
      if (event.data && event.data.size > 0) recordedChunks.push(event.data);
    };

    recorder.onstop = () => {
      if (voiceFrameRef.current) {
        cancelAnimationFrame(voiceFrameRef.current);
        voiceFrameRef.current = null;
      }
      if (mediaRecorderRef.current === recorder) mediaRecorderRef.current = null;
      if (!voiceActiveRef.current || voiceSessionRef.current !== sessionId) return;

      if (!speechDetected || recordedChunks.length === 0) {
        voicePhaseRef.current = 'capture';
        setVoiceState('speech_wait');
        startRecordingCycle(sessionId);
        return;
      }

      const audioBlob = new Blob(recordedChunks, {
        type: recorder.mimeType || mimeType || 'audio/webm',
      });
      if (audioBlob.size < 1000) {
        voicePhaseRef.current = 'capture';
        setVoiceState('speech_wait');
        startRecordingCycle(sessionId);
        return;
      }
      processVoice(sessionId, audioBlob);
    };

    recorder.start(250);
    voicePhaseRef.current = 'capture';
    setVoiceState('speech_wait');

    const monitorMicrophone = () => {
      if (!voiceActiveRef.current || recorder.state === 'inactive') return;

      analyser.getByteTimeDomainData(analyserData);
      let total = 0;
      for (let i = 0; i < analyserData.length; i += 1) {
        const sample = (analyserData[i] - 128) / 128;
        total += sample * sample;
      }

      const volume = Math.sqrt(total / analyserData.length);
      const now = performance.now();
      const hasSpeech = volume >= (speechDetected ? 0.012 : 0.025);

      if (!speechDetected) {
        if (hasSpeech) {
          if (!speechCandidateAt) speechCandidateAt = now;
          if (now - speechCandidateAt >= 250) {
            speechDetected = true;
            speechStartedAt = now;
            voicePhaseRef.current = 'listening';
            setVoiceState('listening');
          }
        } else {
          speechCandidateAt = 0;
        }

        if (!speechDetected && now - cycleStartedAt >= 30000) {
          recorder.stop();
          return;
        }
      } else {
        if (hasSpeech) {
          silenceStartedAt = 0;
        } else if (!silenceStartedAt) {
          silenceStartedAt = now;
        } else if (now - silenceStartedAt >= 3600) {
          recorder.stop();
          return;
        }

        if (now - speechStartedAt >= 40000) {
          recorder.stop();
          return;
        }
      }

      voiceFrameRef.current = requestAnimationFrame(monitorMicrophone);
    };

    voiceFrameRef.current = requestAnimationFrame(monitorMicrophone);
  };

  const toggleVoice = async () => {
    if (!activeSessionId) return;
    if (voiceActive) {
      await stopVoice(activeSessionId);
      return;
    }

    try {
      if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
        throw new Error('Microphone access requires HTTPS. Use the ngrok HTTPS URL.');
      }
      if (!window.MediaRecorder) {
        throw new Error('This browser does not support microphone recording.');
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      const audioContext = new AudioContextClass();
      await audioContext.resume();
      const source = audioContext.createMediaStreamSource(stream);
      const analyser = audioContext.createAnalyser();
      const mute = audioContext.createGain();
      mute.gain.value = 0;
      analyser.fftSize = 2048;
      source.connect(analyser);
      analyser.connect(mute);
      mute.connect(audioContext.destination);

      const res = await fetch('/api/voice/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: activeSessionId }),
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        stream.getTracks().forEach(track => track.stop());
        await audioContext.close();
        throw new Error(data.error || 'Unable to start voice mode');
      }

      mediaStreamRef.current = stream;
      audioContextRef.current = audioContext;
      analyserRef.current = analyser;
      voiceSessionRef.current = activeSessionId;
      voiceActiveRef.current = true;
      voicePhaseRef.current = 'capture';
      setVoiceActive(true);
      setVoiceState('speech_wait');
      startRecordingCycle(activeSessionId);
    } catch (error) {
      cleanupVoice();
      alert(error.message || 'Unable to start voice mode');
    }
  };

  useEffect(() => () => {
    voiceActiveRef.current = false;
    cleanupVoice();
  }, []);

  // ── Load existing session ─────────────────────────────────────────────────

  const loadSession = async (sessionId) => {
    if (isLoading) return;
    // Stop voice for current session before switching
    if (voiceActive && activeSessionId) {
      await stopVoice(activeSessionId);
    }
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
    // Stop voice for current session before creating new one
    if (voiceActive && activeSessionId) {
      await stopVoice(activeSessionId);
    }
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
    setExpandedEvents(prev => ({ ...prev, [idx]: prev[idx] === true ? false : true }));
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
          <div className="chat-bubble chat-bubble-final">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
          </div>
          <div className="chat-msg-time">{msg.time}</div>
        </div>
      );
    }

    if (msg.type === 'tool_result') {
      const expanded = expandedEvents[idx] === true; // default collapsed
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
      const expanded = expandedEvents[idx] === true; // default collapsed
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

  const activeSession = sessions.find(sess => sess.id === activeSessionId);
  const isAgentBusy = isLoading || Boolean(activeSession?.is_running) || (voiceActive && ['agent_wait', 'processing'].includes(voiceState));
  const inputLocked = voiceActive || isAgentBusy;
  const voiceButtonLocked = !activeSessionId || (!voiceActive && isAgentBusy);

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

              {(isLoading || (voiceActive && voiceState === 'agent_wait')) && (
                <div className="chat-thinking">
                  <span className="chat-thinking-dots">AI is thinking</span>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            <div className="chat-input-bar">
              {voiceActive && (
                <div className="voice-state-indicator">
                  {voiceState === 'speech_wait'  && '🎤 Waiting for speech...'}
                  {voiceState === 'listening'    && '🎤 Listening…'}
                  {voiceState === 'transcribing' && '✍️ Transcribing…'}
                  {voiceState === 'agent_wait'   && '⏳ Waiting for agent response…'}
                  {voiceState === 'processing'   && '⚙️ Processing…'}
                  {voiceState === 'speaking'     && '🔊 Speaking…'}
                </div>
              )}
              <div className="chat-input-row">
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
                  placeholder={voiceActive ? 'Voice mode active' : 'Message your home AI…'}
                  disabled={inputLocked}
                />
                <button
                  className={`chat-voice-btn${voiceActive ? ' active' : ''}`}
                  onClick={toggleVoice}
                  disabled={voiceButtonLocked}
                  title={voiceActive ? 'Stop voice mode' : 'Start voice mode'}
                >
                  🎤
                </button>
                <button
                  className="chat-send-btn"
                  onClick={sendMessage}
                  disabled={inputLocked || !inputText.trim()}
                >
                  {isLoading ? '…' : 'Send'}
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default ChatTab;
