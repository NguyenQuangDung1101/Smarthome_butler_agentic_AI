import React, { useState, useEffect, useCallback } from 'react';

// Valid device mapping mirrors the house definition
const DEVICE_MAP = {
  1: {
    room: 'Livingroom',
    devices: [
      { name: 'led1',   desc: 'Light',  type: 'bool' },
      { name: 'motor1', desc: 'Fan',    type: 'int'  },
    ],
  },
  2: {
    room: 'Hallway',
    devices: [
      { name: 'led1',   desc: 'Left Light', type: 'bool' },
      { name: 'led2',   desc: 'Right Light',type: 'bool' },
      { name: 'motor1', desc: 'Fan',         type: 'int'  },
      { name: 'motor2', desc: 'Door',        type: 'int'  },
    ],
  },
  3: {
    room: 'Bedroom + Balcony',
    devices: [
      { name: 'led1',   desc: 'Room Light',        type: 'bool' },
      { name: 'led2',   desc: 'Bed Light',          type: 'bool' },
      { name: 'led3',   desc: 'Balcony Light',      type: 'bool' },
      { name: 'motor1', desc: 'Fan',                type: 'int'  },
      { name: 'motor2', desc: 'Curtain (0=close)',  type: 'int'  },
      { name: 'servo',  desc: 'Lock',               type: 'bool' },
      { name: 'pump',   desc: 'Bonsai Water Pump',  type: 'bool' },
    ],
  },
};

const getDeviceType = (espID, deviceName) =>
  DEVICE_MAP[espID]?.devices.find(d => d.name === deviceName)?.type ?? null;

const nowDatetime = () => {
  const n = new Date();
  const p = v => String(v).padStart(2, '0');
  return `${n.getFullYear()}-${p(n.getMonth() + 1)}-${p(n.getDate())} ${p(n.getHours())}:${p(n.getMinutes())}:${p(n.getSeconds())}`;
};

const emptyForm = () => ({
  datetime: nowDatetime(),
  espID: 1,
  device_name: 'led1',
  value: true,
  executed: false,
});

const DT_RE = /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/;

// ─── Value input ────────────────────────────────────────────────────────────
const ValueInput = ({ espID, deviceName, value, onChange }) => {
  const type = getDeviceType(espID, deviceName);
  if (type === 'bool') {
    return (
      <select value={String(value)} onChange={e => onChange(e.target.value === 'true')} className="sched-input">
        <option value="true">True (On)</option>
        <option value="false">False (Off)</option>
      </select>
    );
  }
  return (
    <input
      type="number" min={0} max={100}
      value={value}
      onChange={e => onChange(e.target.value)}
      className="sched-input"
      style={{ width: '80px' }}
    />
  );
};

// ─── Inline form (shared by add + edit) ─────────────────────────────────────
const SchedForm = ({ form, setForm, onSubmit, onCancel, submitLabel, statusMsg }) => {
  const devices = DEVICE_MAP[form.espID]?.devices ?? [];

  const changeEsp = id => {
    const devs = DEVICE_MAP[id]?.devices ?? [];
    const first = devs[0];
    setForm(f => ({ ...f, espID: Number(id), device_name: first?.name ?? '', value: first?.type === 'bool' ? true : 50 }));
  };

  const changeDevice = name => {
    const t = getDeviceType(form.espID, name);
    setForm(f => ({ ...f, device_name: name, value: t === 'bool' ? true : 50 }));
  };

  return (
    <div className="schedule-form-box">
      <div className="schedule-form-grid">
        <label className="sched-label">
          Datetime <span className="sched-hint">(YYYY-MM-DD HH:MM:SS)</span>
          <input
            type="text"
            value={form.datetime}
            onChange={e => setForm(f => ({ ...f, datetime: e.target.value }))}
            className="sched-input"
            placeholder="2026-01-01 08:00:00"
          />
        </label>

        <label className="sched-label">
          Room (ESP)
          <select value={form.espID} onChange={e => changeEsp(e.target.value)} className="sched-input">
            {Object.entries(DEVICE_MAP).map(([id, info]) => (
              <option key={id} value={id}>ESP{id} – {info.room}</option>
            ))}
          </select>
        </label>

        <label className="sched-label">
          Device
          <select value={form.device_name} onChange={e => changeDevice(e.target.value)} className="sched-input">
            {devices.map(d => (
              <option key={d.name} value={d.name}>{d.name} – {d.desc}</option>
            ))}
          </select>
        </label>

        <label className="sched-label">
          Value
          <ValueInput
            espID={form.espID}
            deviceName={form.device_name}
            value={form.value}
            onChange={v => setForm(f => ({ ...f, value: v }))}
          />
        </label>

        <label className="sched-label sched-check-label">
          <input
            type="checkbox"
            checked={form.executed}
            onChange={e => setForm(f => ({ ...f, executed: e.target.checked }))}
            style={{ marginRight: '6px' }}
          />
          Mark as Executed
        </label>
      </div>

      <div className="sched-form-btns">
        <button className="update-btn sched-submit-btn" onClick={onSubmit}>{submitLabel}</button>
        {onCancel && (
          <button className="refresh-btn sched-cancel-btn" onClick={onCancel}>Cancel</button>
        )}
        {statusMsg && (
          <span className={`note-status ${statusMsg.toLowerCase().includes('error') || statusMsg.toLowerCase().includes('invalid') || statusMsg.toLowerCase().includes('missing') ? 'status-err' : 'status-ok'}`}>
            {statusMsg}
          </span>
        )}
      </div>
    </div>
  );
};

// ─── Main component ──────────────────────────────────────────────────────────
const ScheduleTab = () => {
  const [schedules, setSchedules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState('all');
  const [showAddForm, setShowAddForm] = useState(false);
  const [addForm, setAddForm] = useState(emptyForm());
  const [addStatus, setAddStatus] = useState('');
  const [editingIndex, setEditingIndex] = useState(null);
  const [editForm, setEditForm] = useState(null);

  const fetchSchedules = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/schedules');
      const data = await res.json();
      if (data.success) { setSchedules(data.data); setError(''); }
      else setError(data.error || 'Failed to load schedules');
    } catch { setError('Network error'); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchSchedules(); }, [fetchSchedules]);

  // ── coerce value based on device type ─────────────────────────────────────
  const coerceValue = (espID, deviceName, raw) => {
    const type = getDeviceType(espID, deviceName);
    if (type === 'bool') return raw === true || raw === 'true';
    const n = parseInt(raw, 10);
    return isNaN(n) ? null : n;
  };

  const validateForm = (form) => {
    if (!DT_RE.test(form.datetime)) return 'Invalid datetime format. Use YYYY-MM-DD HH:MM:SS';
    const v = coerceValue(form.espID, form.device_name, form.value);
    if (v === null) return 'Value must be a valid integer 0–100';
    const type = getDeviceType(form.espID, form.device_name);
    if (type === 'int' && (v < 0 || v > 100)) return 'Integer value must be in range 0–100';
    return null;
  };

  // ── Add ───────────────────────────────────────────────────────────────────
  const handleAdd = async () => {
    const err = validateForm(addForm);
    if (err) { setAddStatus(err); return; }
    const value = coerceValue(addForm.espID, addForm.device_name, addForm.value);
    setAddStatus('Saving...');
    try {
      const res = await fetch('/api/schedules', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          datetime: addForm.datetime,
          appliance_control: {
            espID: addForm.espID, device_type: 'actuator',
            device_name: addForm.device_name, action: 'set', value,
          },
          executed: addForm.executed,
        }),
      });
      const data = await res.json();
      if (data.success) {
        setAddStatus('Schedule added!');
        setAddForm(emptyForm());
        setShowAddForm(false);
        fetchSchedules();
        setTimeout(() => setAddStatus(''), 2500);
      } else {
        setAddStatus(data.error || 'Error');
      }
    } catch { setAddStatus('Network error'); }
  };

  // ── Edit save ─────────────────────────────────────────────────────────────
  const handleEditSave = async (index) => {
    const err = validateForm(editForm);
    if (err) { alert(err); return; }
    const value = coerceValue(editForm.espID, editForm.device_name, editForm.value);
    try {
      const res = await fetch(`/api/schedules/${index}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          datetime: editForm.datetime,
          appliance_control: {
            espID: editForm.espID, device_type: 'actuator',
            device_name: editForm.device_name, action: 'set', value,
          },
          executed: editForm.executed,
        }),
      });
      const data = await res.json();
      if (data.success) { setEditingIndex(null); fetchSchedules(); }
      else alert(data.error || 'Failed to update');
    } catch { alert('Network error'); }
  };

  // ── Delete ────────────────────────────────────────────────────────────────
  const handleDelete = async (index) => {
    if (!window.confirm('Delete this schedule entry?')) return;
    try {
      const res = await fetch(`/api/schedules/${index}`, { method: 'DELETE' });
      const data = await res.json();
      if (data.success) fetchSchedules();
      else alert(data.error || 'Failed to delete');
    } catch { alert('Network error'); }
  };

  const startEdit = (index) => {
    const s = schedules[index];
    const ctrl = s.appliance_control;
    setEditForm({ datetime: s.datetime, espID: ctrl.espID, device_name: ctrl.device_name, value: ctrl.value, executed: s.executed });
    setEditingIndex(index);
  };

  const roomLabel = (espID) => DEVICE_MAP[espID]?.room ?? `ESP${espID}`;
  const deviceDesc = (espID, name) => {
    const d = DEVICE_MAP[espID]?.devices.find(d => d.name === name);
    return d ? `${name} (${d.desc})` : name;
  };
  const fmtValue = (v) => typeof v === 'boolean' ? (v ? 'ON' : 'OFF') : v;

  const filtered = schedules
    .map((s, i) => ({ ...s, _idx: i }))
    .filter(s => filter === 'all' ? true : filter === 'pending' ? !s.executed : s.executed);

  const pendingCount = schedules.filter(s => !s.executed).length;
  const executedCount = schedules.filter(s => s.executed).length;

  return (
    <div className="tab-content">
      <div className="header-action">
        <h2>Schedule Triggers</h2>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button className="note-edit-btn" style={{ padding: '8px 16px' }} onClick={() => { setShowAddForm(v => !v); setAddStatus(''); }}>
            {showAddForm ? '▲ Hide Form' : '＋ Add Schedule'}
          </button>
          <button className="refresh-btn" onClick={fetchSchedules}>Refresh</button>
        </div>
      </div>

      {/* Add form */}
      {showAddForm && (
        <SchedForm
          form={addForm}
          setForm={setAddForm}
          onSubmit={handleAdd}
          onCancel={() => { setShowAddForm(false); setAddStatus(''); }}
          submitLabel="Add Schedule"
          statusMsg={addStatus}
        />
      )}

      {/* Stats + Filter */}
      <div className="schedule-filter">
        <span className="sched-stats">
          Total: <strong>{schedules.length}</strong> &nbsp;|&nbsp;
          Pending: <strong style={{ color: '#e67e22' }}>{pendingCount}</strong> &nbsp;|&nbsp;
          Executed: <strong style={{ color: '#27ae60' }}>{executedCount}</strong>
        </span>
        <div className="filter-btns">
          {['all', 'pending', 'executed'].map(f => (
            <button
              key={f}
              className={`filter-btn ${filter === f ? 'active' : ''}`}
              onClick={() => setFilter(f)}
            >
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {loading && <div className="no-data">Loading schedules...</div>}
      {!loading && error && <div style={{ color: '#dc3545', padding: '8px' }}>{error}</div>}
      {!loading && !error && filtered.length === 0 && (
        <div className="no-data">No {filter === 'all' ? '' : filter + ' '}schedules found.</div>
      )}

      <div className="schedule-list">
        {filtered.map(s => {
          const ctrl = s.appliance_control;
          const idx = s._idx;
          const isEditing = editingIndex === idx;
          return (
            <div key={idx} className={`schedule-item ${s.executed ? 'sched-executed' : 'sched-pending'}`}>
              {isEditing && editForm ? (
                <SchedForm
                  form={editForm}
                  setForm={setEditForm}
                  onSubmit={() => handleEditSave(idx)}
                  onCancel={() => setEditingIndex(null)}
                  submitLabel="Save Changes"
                  statusMsg=""
                />
              ) : (
                <div className="schedule-item-inner">
                  <div className="sched-row-left">
                    <span className={`sched-badge ${s.executed ? 'badge-done' : 'badge-pending'}`}>
                      {s.executed ? '✓ Executed' : '⏳ Pending'}
                    </span>
                    <span className="sched-index-label">#{idx}</span>
                    <span className="sched-datetime">{s.datetime}</span>
                  </div>
                  <div className="sched-row-right">
                    <span className="sched-room">{roomLabel(ctrl.espID)}</span>
                    <span className="sched-arrow">›</span>
                    <span className="sched-device">{deviceDesc(ctrl.espID, ctrl.device_name)}</span>
                    <span className="sched-arrow">→</span>
                    <span className={`sched-value ${typeof ctrl.value === 'boolean' ? (ctrl.value ? 'val-on' : 'val-off') : 'val-num'}`}>
                      {fmtValue(ctrl.value)}
                    </span>
                  </div>
                  <div className="sched-item-actions">
                    <button className="note-edit-btn" onClick={() => startEdit(idx)}>Edit</button>
                    <button className="note-delete-btn" onClick={() => handleDelete(idx)}>Delete</button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default ScheduleTab;
