import React, { useState, useEffect, useRef, useCallback } from 'react';

// ─── helpers ────────────────────────────────────────────────────────────────

const fmt = (v) => {
  if (v === null || v === undefined) return '—';
  if (typeof v === 'object') return JSON.stringify(v, null, 2);
  return String(v);
};

// ─── sub-components ──────────────────────────────────────────────────────────

const StatusBadge = ({ running, paused }) => {
  if (running && !paused) return <span className="ss-badge ss-badge-running">● Running</span>;
  if (running && paused)  return <span className="ss-badge ss-badge-paused">⏸ Paused</span>;
  return <span className="ss-badge ss-badge-stopped">■ Stopped</span>;
};

// ─── main component ──────────────────────────────────────────────────────────

const ScheduleSessionTab = ({ onPendingPermissionsChange }) => {
  // ── loop status ──────────────────────────────────────────────────────────
  const [loopStatus, setLoopStatus] = useState({ running: false, paused: false, thread_alive: false });

  const fetchLoopStatus = useCallback(async () => {
    try {
      const r = await fetch('/api/schedule-loop/status');
      if (r.ok) setLoopStatus(await r.json());
    } catch (_) {}
  }, []);

  useEffect(() => {
    fetchLoopStatus();
    const id = setInterval(fetchLoopStatus, 3000);
    return () => clearInterval(id);
  }, [fetchLoopStatus]);

  const handleStart  = async () => { await fetch('/api/schedule-loop/start', { method: 'POST' }); fetchLoopStatus(); };
  const handleStop   = async () => { await fetch('/api/schedule-loop/stop',  { method: 'POST' }); fetchLoopStatus(); };
  const handlePause  = async () => { await fetch('/api/schedule-loop/pause', { method: 'POST' }); fetchLoopStatus(); };

  // ── history ───────────────────────────────────────────────────────────────
  const [history, setHistory] = useState([]);
  const [expandedHistory, setExpandedHistory] = useState({});

  const fetchHistory = useCallback(async () => {
    try {
      const r = await fetch('/api/schedule-loop/history');
      if (r.ok) setHistory(await r.json());
    } catch (_) {}
  }, []);

  useEffect(() => {
    fetchHistory();
    const id = setInterval(fetchHistory, 5000);
    return () => clearInterval(id);
  }, [fetchHistory]);

  const toggleHistory = (id) => setExpandedHistory(prev => ({ ...prev, [id]: !prev[id] }));

  // ── permission requests ───────────────────────────────────────────────────
  const [permissions, setPermissions] = useState([]);
  const [permResponses, setPermResponses] = useState({});

  const fetchPermissions = useCallback(async () => {
    try {
      const r = await fetch('/api/schedule-loop/permissions');
      if (r.ok) {
        const data = await r.json();
        setPermissions(data);
        const pending = data.filter(p => p.status === 'pending').length;
        if (onPendingPermissionsChange) onPendingPermissionsChange(pending);
      }
    } catch (_) {}
  }, [onPendingPermissionsChange]);

  useEffect(() => {
    fetchPermissions();
    const id = setInterval(fetchPermissions, 3000);
    return () => clearInterval(id);
  }, [fetchPermissions]);

  const handleRespond = async (req_id) => {
    const text = (permResponses[req_id] || '').trim();
    if (!text) return;
    await fetch(`/api/schedule-loop/permissions/${req_id}/respond`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ response: text }),
    });
    setPermResponses(prev => { const n = { ...prev }; delete n[req_id]; return n; });
    fetchPermissions();
  };

  // ── weekday_weekend.json editor ───────────────────────────────────────────
  const [schedJson, setSchedJson] = useState('');
  const [schedJsonError, setSchedJsonError] = useState('');
  const [schedSaveStatus, setSchedSaveStatus] = useState('');
  const textareaRef = useRef(null);

  const fetchSchedJson = useCallback(async () => {
    try {
      const r = await fetch('/api/weekday-weekend');
      if (r.ok) {
        const d = await r.json();
        if (d.success) setSchedJson(JSON.stringify(d.data, null, 2));
      }
    } catch (_) {}
  }, []);

  useEffect(() => { fetchSchedJson(); }, [fetchSchedJson]);

  const handleSchedSave = async () => {
    setSchedJsonError('');
    setSchedSaveStatus('');
    let parsed;
    try {
      parsed = JSON.parse(schedJson);
    } catch (e) {
      setSchedJsonError('Invalid JSON: ' + e.message);
      return;
    }
    try {
      const r = await fetch('/api/weekday-weekend', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(parsed),
      });
      const d = await r.json();
      if (d.success) {
        setSchedSaveStatus('Saved successfully!');
      } else {
        setSchedJsonError(d.error || 'Save failed');
      }
    } catch (e) {
      setSchedJsonError('Network error: ' + e.message);
    }
    setTimeout(() => setSchedSaveStatus(''), 3000);
  };

  const handleSchedFormat = () => {
    try {
      setSchedJson(JSON.stringify(JSON.parse(schedJson), null, 2));
      setSchedJsonError('');
    } catch (e) {
      setSchedJsonError('Invalid JSON: ' + e.message);
    }
  };

  // ── active section ────────────────────────────────────────────────────────
  const [activeSection, setActiveSection] = useState('monitor');

  // ── render ────────────────────────────────────────────────────────────────
  return (
    <div className="ss-root">
      {/* ── top bar ── */}
      <div className="ss-topbar">
        <div className="ss-topbar-left">
          <h2 className="ss-title">Schedule Session</h2>
          <StatusBadge running={loopStatus.running} paused={loopStatus.paused} />
        </div>
        <div className="ss-topbar-right">
          {!loopStatus.running && (
            <button className="ss-btn ss-btn-start" onClick={handleStart}>▶ Start Loop</button>
          )}
          {loopStatus.running && (
            <>
              <button className="ss-btn ss-btn-pause" onClick={handlePause}>
                {loopStatus.paused ? '▶ Resume' : '⏸ Pause'}
              </button>
              <button className="ss-btn ss-btn-stop" onClick={handleStop}>■ Stop Loop</button>
            </>
          )}
        </div>
      </div>

      {/* ── permission alerts ── */}
      {permissions.filter(p => p.status === 'pending').length > 0 && (
        <div className="ss-perm-alert-banner">
          ⚠️ {permissions.filter(p => p.status === 'pending').length} appliance setting(s) require your confirmation before execution!
        </div>
      )}

      {/* ── section tabs ── */}
      <div className="ss-section-tabs">
        <button
          className={`ss-section-btn${activeSection === 'monitor' ? ' active' : ''}`}
          onClick={() => setActiveSection('monitor')}
        >
          Monitor
          {permissions.filter(p => p.status === 'pending').length > 0 && (
            <span className="ss-perm-badge">{permissions.filter(p => p.status === 'pending').length}</span>
          )}
        </button>
        <button
          className={`ss-section-btn${activeSection === 'editor' ? ' active' : ''}`}
          onClick={() => setActiveSection('editor')}
        >Schedule Editor</button>
      </div>

      {/* ══ MONITOR SECTION ══════════════════════════════════════════════════ */}
      {activeSection === 'monitor' && (
        <div className="ss-monitor">

          {/* permission requests */}
          {permissions.filter(p => p.status === 'pending').length > 0 && (
            <div className="ss-perm-section">
              <h3 className="ss-section-heading">⚠️ Pending Permission Requests</h3>
              {permissions.filter(p => p.status === 'pending').map(req => (
                <div key={req.id} className="ss-perm-card">
                  <div className="ss-perm-time">{req.time}</div>
                  <div className="ss-perm-context">{req.context}</div>
                  <div className="ss-perm-respond-row">
                    <input
                      className="ss-perm-input"
                      type="text"
                      placeholder="Type your confirmation / response…"
                      value={permResponses[req.id] || ''}
                      onChange={e => setPermResponses(prev => ({ ...prev, [req.id]: e.target.value }))}
                      onKeyDown={e => { if (e.key === 'Enter') handleRespond(req.id); }}
                    />
                    <button className="ss-btn ss-btn-confirm" onClick={() => handleRespond(req.id)}>Confirm</button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* past permissions */}
          {permissions.filter(p => p.status !== 'pending').length > 0 && (
            <details className="ss-past-perms">
              <summary className="ss-past-perms-summary">Past Permission Requests ({permissions.filter(p => p.status !== 'pending').length})</summary>
              {permissions.filter(p => p.status !== 'pending').map(req => (
                <div key={req.id} className="ss-perm-card ss-perm-card-done">
                  <div className="ss-perm-time">{req.time} <span className={`ss-perm-status ${req.status}`}>{req.status}</span></div>
                  <div className="ss-perm-context" style={{ opacity: 0.7 }}>{req.context}</div>
                </div>
              ))}
            </details>
          )}

          {/* inference history */}
          <div className="ss-history-header">
            <h3 className="ss-section-heading">Inference History</h3>
            <button className="ss-btn ss-btn-refresh" onClick={fetchHistory}>↻ Refresh</button>
          </div>

          {history.length === 0 && (
            <div className="ss-empty">No inference history yet.</div>
          )}

          {history.map(entry => (
            <div key={entry.id} className="ss-history-card">
              <div className="ss-history-header-row" onClick={() => toggleHistory(entry.id)}>
                <div className="ss-history-header-left">
                  <span className="ss-history-time">{entry.date_time}</span>
                  {entry.appliance_execute && (
                    <span className="ss-history-tag ss-tag-appliance">⚡ Appliance Executed</span>
                  )}
                </div>
                <span className="ss-history-toggle">{expandedHistory[entry.id] ? '▲' : '▼'}</span>
              </div>
              {expandedHistory[entry.id] && (
                <div className="ss-history-body">
                  {entry.moment && (
                    <div className="ss-history-block">
                      <div className="ss-history-block-label">Moment</div>
                      <pre className="ss-pre">{fmt(entry.moment)}</pre>
                    </div>
                  )}
                  {entry.user_context && (
                    <div className="ss-history-block">
                      <div className="ss-history-block-label">User Confirmation</div>
                      <div className="ss-history-result">{entry.user_context}</div>
                    </div>
                  )}
                  {entry.result && (
                    <div className="ss-history-block">
                      <div className="ss-history-block-label">Agent Response</div>
                      <div className="ss-history-result">{entry.result}</div>
                    </div>
                  )}
                  {entry.appliance_execute && (
                    <div className="ss-history-block">
                      <div className="ss-history-block-label">Appliance Execution</div>
                      <pre className="ss-pre">{fmt(entry.appliance_execute)}</pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* ══ EDITOR SECTION ═══════════════════════════════════════════════════ */}
      {activeSection === 'editor' && (
        <div className="ss-editor">
          <div className="ss-editor-toolbar">
            <span className="ss-editor-filename">scheduler/weekday_weekend.json</span>
            <button className="ss-btn ss-btn-format" onClick={handleSchedFormat}>{ } Format</button>
            <button className="ss-btn ss-btn-reload" onClick={fetchSchedJson}>↻ Reload</button>
            <button className="ss-btn ss-btn-save" onClick={handleSchedSave}>Save</button>
          </div>
          {schedJsonError && <div className="ss-editor-error">⚠ {schedJsonError}</div>}
          {schedSaveStatus && <div className="ss-editor-ok">✔ {schedSaveStatus}</div>}
          <textarea
            ref={textareaRef}
            className="ss-json-textarea"
            value={schedJson}
            onChange={e => { setSchedJson(e.target.value); setSchedJsonError(''); setSchedSaveStatus(''); }}
            spellCheck={false}
          />
        </div>
      )}
    </div>
  );
};

export default ScheduleSessionTab;
