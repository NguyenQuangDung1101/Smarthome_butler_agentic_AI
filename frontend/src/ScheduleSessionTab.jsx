import React, { useState, useEffect, useRef, useCallback } from 'react';

// ─── helpers ────────────────────────────────────────────────────────────────

const fmt = (v) => {
  if (v === null || v === undefined) return '—';
  if (typeof v === 'object') return JSON.stringify(v, null, 2);
  return String(v);
};

// ─── actuator catalog ────────────────────────────────────────────────────────

const KNOWN_ACTUATORS = {
  1: [
    { id: 'led1',   label: 'Light',          type: 'boolean' },
    { id: 'motor1', label: 'Fan',            type: 'integer' },
  ],
  2: [
    { id: 'led1',   label: 'Left Light',     type: 'boolean' },
    { id: 'led2',   label: 'Right Light',    type: 'boolean' },
    { id: 'motor1', label: 'Fan',            type: 'integer' },
    { id: 'motor2', label: 'Main Door',      type: 'integer' },
  ],
  3: [
    { id: 'led1',   label: 'Room Light',     type: 'boolean' },
    { id: 'led2',   label: 'Bed Light',      type: 'boolean' },
    { id: 'led3',   label: 'Balcony Light',  type: 'boolean' },
    { id: 'motor1', label: 'Fan',            type: 'integer' },
    { id: 'motor2', label: 'Curtain',        type: 'integer' },
    { id: 'servo',  label: 'Door Lock',      type: 'boolean' },
    { id: 'pump',   label: 'Bonsai Pump',    type: 'boolean' },
  ],
};

const ESP_LABELS = {
  1: 'Living Room (ESP 1)',
  2: 'Hallway (ESP 2)',
  3: 'Bedroom / Balcony (ESP 3)',
};

const getActuatorInfo = (espID, actuator_id) =>
  (KNOWN_ACTUATORS[espID] || []).find(a => a.id === actuator_id) || null;

const defaultValueForType = (type) => type === 'boolean' ? false : 0;

const defaultNewAppliance = () => {
  const firstAct = KNOWN_ACTUATORS[1][0];
  return { espID: 1, actuator_id: firstAct.id, value: defaultValueForType(firstAct.type), note: firstAct.label };
};

// ─── ApplianceEditorRow ───────────────────────────────────────────────────────

const ApplianceEditorRow = ({ ap, onChange, onRemove }) => {
  const espID = ap.espID || 1;
  const actuators = KNOWN_ACTUATORS[espID] || [];
  const info = getActuatorInfo(espID, ap.actuator_id);
  const valueType = info ? info.type : (typeof ap.value === 'boolean' ? 'boolean' : 'integer');

  const handleEspChange = (newEsp) => {
    const newEspInt = parseInt(newEsp);
    const list = KNOWN_ACTUATORS[newEspInt] || [];
    const first = list[0];
    onChange({
      ...ap,
      espID: newEspInt,
      actuator_id: first ? first.id : '',
      value: first ? defaultValueForType(first.type) : false,
      note: first ? first.label : '',
    });
  };

  const handleActuatorChange = (newActId) => {
    const newInfo = getActuatorInfo(espID, newActId);
    onChange({
      ...ap,
      actuator_id: newActId,
      value: newInfo ? defaultValueForType(newInfo.type) : ap.value,
      note: newInfo ? newInfo.label : ap.note,
    });
  };

  return (
    <tr>
      <td>
        <select className="ss-ap-input ss-ap-loc-sel" value={espID}
          onChange={e => handleEspChange(e.target.value)}>
          {Object.entries(ESP_LABELS).map(([id, lbl]) => (
            <option key={id} value={id}>{lbl}</option>
          ))}
        </select>
      </td>
      <td>
        <select className="ss-ap-input ss-ap-act-sel" value={ap.actuator_id}
          onChange={e => handleActuatorChange(e.target.value)}>
          {actuators.map(a => (
            <option key={a.id} value={a.id}>{a.label} ({a.id})</option>
          ))}
          {actuators.length === 0 && <option value="">--</option>}
        </select>
      </td>
      <td>
        {valueType === 'boolean' ? (
          <select className="ss-ap-input ss-ap-bool"
            value={String(ap.value)}
            onChange={e => onChange({ ...ap, value: e.target.value === 'true' })}>
            <option value="true">ON</option>
            <option value="false">OFF</option>
          </select>
        ) : (
          <div className="ss-ap-int-row">
            <input className="ss-ap-input ss-ap-num" type="number" min="0" max="100"
              value={ap.value}
              onChange={e => onChange({ ...ap, value: Number(e.target.value) })} />
            <span className="ss-ap-pct">%</span>
          </div>
        )}
      </td>
      <td>
        <input className="ss-ap-input ss-ap-note" type="text" value={ap.note}
          onChange={e => onChange({ ...ap, note: e.target.value })} />
      </td>
      <td>
        <button className="ss-btn ss-btn-remove-sm" onClick={onRemove}>Remove</button>
      </td>
    </tr>
  );
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
  const [schedData, setSchedData] = useState(null);
  const [editorSubTab, setEditorSubTab] = useState('weekday');
  const [expandedEntries, setExpandedEntries] = useState({});
  const textareaRef = useRef(null);

  const fetchSchedJson = useCallback(async () => {
    try {
      const r = await fetch('/api/weekday-weekend');
      if (r.ok) {
        const d = await r.json();
        if (d.success) {
          setSchedJson(JSON.stringify(d.data, null, 2));
          setSchedData(d.data);
        }
      }
    } catch (_) {}
  }, []);

  useEffect(() => { fetchSchedJson(); }, [fetchSchedJson]);

  const updateScheduleData = (newData) => {
    setSchedData(newData);
    setSchedJson(JSON.stringify(newData, null, 2));
    setSchedJsonError('');
    setSchedSaveStatus('');
  };

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
          {/* Toolbar */}
          <div className="ss-editor-toolbar">
            <span className="ss-editor-filename">scheduler/weekday_weekend.json</span>
            <button className="ss-btn ss-btn-reload" onClick={fetchSchedJson}>Reload</button>
            <button className="ss-btn ss-btn-save" onClick={handleSchedSave}>Save</button>
          </div>
          {schedJsonError && <div className="ss-editor-error">{schedJsonError}</div>}
          {schedSaveStatus && <div className="ss-editor-ok">{schedSaveStatus}</div>}

          {/* Weekday / Weekend sub-tabs */}
          <div className="ss-editor-subtabs">
            <button
              className={`ss-editor-subtab${editorSubTab === 'weekday' ? ' active' : ''}`}
              onClick={() => setEditorSubTab('weekday')}
            >Weekday</button>
            <button
              className={`ss-editor-subtab${editorSubTab === 'weekend' ? ' active' : ''}`}
              onClick={() => setEditorSubTab('weekend')}
            >Weekend</button>
          </div>

          {!schedData && <div className="ss-empty">Loading schedule data...</div>}

          {schedData && (() => {
            const dayType = editorSubTab;
            const dayData = schedData.schedule[dayType];

            const updateDayData = (newDayData) => {
              updateScheduleData({
                ...schedData,
                schedule: { ...schedData.schedule, [dayType]: newDayData },
              });
            };

            const sortedEntries = [...(dayData.appliance_setting || [])]
              .map((e, i) => ({ ...e, _origIdx: i }))
              .sort((a, b) => a.time.localeCompare(b.time));

            return (
              <div className="ss-structured-editor">

                {/* Applicable Days */}
                <div className="ss-se-section">
                  <div className="ss-se-section-title">Applicable Days</div>
                  <div className="ss-day-chips">
                    {dayData.applicable_days.map(d => (
                      <span key={d} className="ss-day-chip">{d}</span>
                    ))}
                  </div>
                </div>

                {/* Schedule Entries */}
                <div className="ss-se-section">
                  <div className="ss-se-section-header">
                    <div className="ss-se-section-title">
                      Schedule Entries
                      <span className="ss-se-count">{sortedEntries.length} entries</span>
                    </div>
                    <button className="ss-btn ss-btn-add" onClick={() => {
                      const newEntry = { time: '12:00:00', description: 'New entry', note: 'Automatic execution', appliances: [] };
                      updateDayData({ ...dayData, appliance_setting: [...dayData.appliance_setting, newEntry] });
                    }}>Add Entry</button>
                  </div>

                  {sortedEntries.length === 0 && (
                    <div className="ss-empty">No schedule entries. Add one above.</div>
                  )}

                  {sortedEntries.map((entry) => {
                    const origIdx = entry._origIdx;
                    const entryKey = `${dayType}-${origIdx}`;
                    const isExpanded = !!expandedEntries[entryKey];
                    const needsPermission = entry.note !== 'Automatic execution';

                    const updateEntry = (field, value) => {
                      const newSettings = [...dayData.appliance_setting];
                      newSettings[origIdx] = { ...newSettings[origIdx], [field]: value };
                      updateDayData({ ...dayData, appliance_setting: newSettings });
                    };

                    const removeEntry = () => {
                      const newSettings = dayData.appliance_setting.filter((_, i) => i !== origIdx);
                      updateDayData({ ...dayData, appliance_setting: newSettings });
                    };

                    return (
                      <div key={entryKey} className={`ss-entry-card${needsPermission ? ' ss-entry-perm' : ''}`}>
                        {/* Entry header row */}
                        <div className="ss-entry-header">
                          <input
                            className="ss-entry-time"
                            type="time"
                            step="1"
                            value={entry.time.slice(0, 5)}
                            onChange={e => updateEntry('time', e.target.value + ':00')}
                          />
                          <input
                            className="ss-entry-desc"
                            type="text"
                            value={entry.description}
                            onChange={e => updateEntry('description', e.target.value)}
                          />
                          <select
                            className={`ss-entry-exec${needsPermission ? ' ss-exec-perm' : ' ss-exec-auto'}`}
                            value={entry.note}
                            onChange={e => updateEntry('note', e.target.value)}
                          >
                            <option value="Automatic execution">Automatic</option>
                            <option value="Ask for user permission before execute">Requires Permission</option>
                          </select>
                          <button
                            className="ss-btn ss-btn-toggle-entry"
                            onClick={() => setExpandedEntries(prev => ({ ...prev, [entryKey]: !prev[entryKey] }))}
                          >
                            {isExpanded ? 'Collapse' : `Appliances (${entry.appliances.length})`}
                          </button>
                          <button className="ss-btn ss-btn-remove" onClick={removeEntry}>Remove</button>
                        </div>

                        {/* Appliances table (expanded) */}
                        {isExpanded && (
                          <div className="ss-entry-body">
                            {entry.appliances.length === 0 && (
                              <div className="ss-empty ss-empty-sm">No appliances in this entry.</div>
                            )}
                            {entry.appliances.length > 0 && (
                              <table className="ss-ap-table">
                                <thead>
                                  <tr>
                                    <th>Location (ESP)</th>
                                    <th>Actuator</th>
                                    <th>Value</th>
                                    <th>Note</th>
                                    <th></th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {entry.appliances.map((ap, apIdx) => (
                                    <ApplianceEditorRow
                                      key={apIdx}
                                      ap={ap}
                                      onChange={updated => {
                                        const newApps = [...entry.appliances];
                                        newApps[apIdx] = updated;
                                        updateEntry('appliances', newApps);
                                      }}
                                      onRemove={() =>
                                        updateEntry('appliances', entry.appliances.filter((_, i) => i !== apIdx))
                                      }
                                    />
                                  ))}
                                </tbody>
                              </table>
                            )}
                            <button className="ss-btn ss-btn-add-sm" onClick={() => {
                              updateEntry('appliances', [...entry.appliances, defaultNewAppliance()]);
                            }}>Add Appliance</button>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>

                {/* Owner Activity - editable */}
                <div className="ss-se-section">
                  <div className="ss-se-section-header">
                    <div className="ss-se-section-title">
                      Owner Activity
                      <span className="ss-se-count">{dayData.owner_activity.length} activities</span>
                    </div>
                    <button className="ss-btn ss-btn-add" onClick={() => {
                      updateDayData({
                        ...dayData,
                        owner_activity: [...dayData.owner_activity, { activity: 'New activity', description: '', time: '12:00:00' }],
                      });
                    }}>Add Activity</button>
                  </div>
                  {dayData.owner_activity.length === 0 && (
                    <div className="ss-empty ss-empty-sm">No activities.</div>
                  )}
                  {dayData.owner_activity.map((act, idx) => {
                    const hasPeriod = !!act.time_period;

                    const updateAct = (changes) => {
                      const newActs = [...dayData.owner_activity];
                      newActs[idx] = { ...newActs[idx], ...changes };
                      updateDayData({ ...dayData, owner_activity: newActs });
                    };

                    const removeAct = () => {
                      updateDayData({ ...dayData, owner_activity: dayData.owner_activity.filter((_, i) => i !== idx) });
                    };

                    const toggleMode = () => {
                      if (hasPeriod) {
                        const newAct = { activity: act.activity, description: act.description, time: act.time_period.start };
                        const newActs = [...dayData.owner_activity];
                        newActs[idx] = newAct;
                        updateDayData({ ...dayData, owner_activity: newActs });
                      } else {
                        const newAct = { activity: act.activity, description: act.description, time_period: { start: act.time || '08:00:00', end: '09:00:00' } };
                        const newActs = [...dayData.owner_activity];
                        newActs[idx] = newAct;
                        updateDayData({ ...dayData, owner_activity: newActs });
                      }
                    };

                    return (
                      <div key={idx} className="ss-act-edit-row">
                        <div className="ss-act-edit-time">
                          {hasPeriod ? (
                            <div className="ss-act-period">
                              <input type="time" step="1" className="ss-time-mini"
                                value={act.time_period.start.slice(0, 5)}
                                onChange={e => updateAct({ time_period: { ...act.time_period, start: e.target.value + ':00' } })} />
                              <span className="ss-time-sep">to</span>
                              <input type="time" step="1" className="ss-time-mini"
                                value={act.time_period.end.slice(0, 5)}
                                onChange={e => updateAct({ time_period: { ...act.time_period, end: e.target.value + ':00' } })} />
                            </div>
                          ) : (
                            <input type="time" step="1" className="ss-time-mini"
                              value={(act.time || '').slice(0, 5)}
                              onChange={e => updateAct({ time: e.target.value + ':00' })} />
                          )}
                          <button className="ss-btn ss-btn-mode" onClick={toggleMode}>
                            {hasPeriod ? 'Set Point' : 'Set Period'}
                          </button>
                        </div>
                        <div className="ss-act-edit-content">
                          <input type="text" className="ss-ap-input ss-act-name-input"
                            value={act.activity}
                            onChange={e => updateAct({ activity: e.target.value })}
                            placeholder="Activity name" />
                          <input type="text" className="ss-ap-input ss-act-desc-input"
                            value={act.description}
                            onChange={e => updateAct({ description: e.target.value })}
                            placeholder="Description" />
                        </div>
                        <button className="ss-btn ss-btn-remove-sm" onClick={removeAct}>Remove</button>
                      </div>
                    );
                  })}
                </div>

                {/* Initial Settings - editable */}
                <div className="ss-se-section">
                  <div className="ss-se-section-header">
                    <div className="ss-se-section-title">
                      Initial Settings
                      <span className="ss-se-count">applied at midnight ({dayData.initial_settings.time})</span>
                    </div>
                    <div className="ss-init-time-row">
                      <label className="ss-init-time-label">Time:</label>
                      <input
                        type="time"
                        step="1"
                        className="ss-entry-time"
                        value={dayData.initial_settings.time.slice(0, 5)}
                        onChange={e => updateDayData({
                          ...dayData,
                          initial_settings: { ...dayData.initial_settings, time: e.target.value + ':00' },
                        })}
                      />
                      <button className="ss-btn ss-btn-add-sm" onClick={() => {
                        const newApps = [...dayData.initial_settings.appliances, defaultNewAppliance()];
                        updateDayData({ ...dayData, initial_settings: { ...dayData.initial_settings, appliances: newApps } });
                      }}>Add Appliance</button>
                    </div>
                  </div>
                  {dayData.initial_settings.appliances.length === 0 && (
                    <div className="ss-empty ss-empty-sm">No initial appliances.</div>
                  )}
                  {dayData.initial_settings.appliances.length > 0 && (
                    <table className="ss-ap-table">
                      <thead>
                        <tr>
                          <th>Location (ESP)</th>
                          <th>Actuator</th>
                          <th>Value</th>
                          <th>Note</th>
                          <th></th>
                        </tr>
                      </thead>
                      <tbody>
                        {dayData.initial_settings.appliances.map((ap, idx) => (
                          <ApplianceEditorRow
                            key={idx}
                            ap={ap}
                            onChange={updated => {
                              const newApps = [...dayData.initial_settings.appliances];
                              newApps[idx] = updated;
                              updateDayData({ ...dayData, initial_settings: { ...dayData.initial_settings, appliances: newApps } });
                            }}
                            onRemove={() => {
                              const newApps = dayData.initial_settings.appliances.filter((_, i) => i !== idx);
                              updateDayData({ ...dayData, initial_settings: { ...dayData.initial_settings, appliances: newApps } });
                            }}
                          />
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>

              </div>
            );
          })()}
        </div>
      )}
    </div>
  );
};

export default ScheduleSessionTab;
