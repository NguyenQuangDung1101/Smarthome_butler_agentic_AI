import React, { useState, useEffect, useCallback } from 'react';

const NotesTab = () => {
  const [notes, setNotes] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const today = new Date().toISOString().slice(0, 10);
  const [addText, setAddText] = useState('');
  const [addDate, setAddDate] = useState(today);
  const [addStatus, setAddStatus] = useState('');

  const [editingId, setEditingId] = useState(null);
  const [editText, setEditText] = useState('');

  const fetchNotes = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/notes');
      const data = await res.json();
      if (data.success) {
        setNotes(data.data);
        setError('');
      } else {
        setError(data.error || 'Failed to load notes');
      }
    } catch {
      setError('Network error');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchNotes(); }, [fetchNotes]);

  const handleAdd = async () => {
    const text = addText.trim();
    if (!text || !addDate) {
      setAddStatus('Please fill in both date and note text.');
      return;
    }
    setAddStatus('Saving...');
    try {
      const res = await fetch('/api/notes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, dates: [addDate] }),
      });
      const data = await res.json();
      if (data.success) {
        setAddStatus('Note added!');
        setAddText('');
        fetchNotes();
        setTimeout(() => setAddStatus(''), 2500);
      } else {
        setAddStatus(data.error || 'Error saving note');
      }
    } catch {
      setAddStatus('Network error');
    }
  };

  const handleEditSave = async (id) => {
    const text = editText.trim();
    if (!text) return;
    try {
      const res = await fetch(`/api/notes/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      });
      const data = await res.json();
      if (data.success) {
        setEditingId(null);
        fetchNotes();
      } else {
        alert(data.error || 'Failed to update note');
      }
    } catch {
      alert('Network error');
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this note?')) return;
    try {
      const res = await fetch(`/api/notes/${id}`, { method: 'DELETE' });
      const data = await res.json();
      if (data.success) {
        fetchNotes();
      } else {
        alert(data.error || 'Failed to delete note');
      }
    } catch {
      alert('Network error');
    }
  };

  const sortedDates = Object.keys(notes).sort((a, b) => b.localeCompare(a));

  return (
    <div className="tab-content">
      <div className="header-action">
        <h2>Note Storage</h2>
        <button className="refresh-btn" onClick={fetchNotes}>Refresh</button>
      </div>

      {/* Add Note Form */}
      <div className="note-add-form">
        <h3 style={{ marginTop: 0, marginBottom: '12px' }}>Add New Note</h3>
        <div className="note-add-row">
          <input
            type="date"
            value={addDate}
            onChange={e => setAddDate(e.target.value)}
            className="note-date-input"
          />
          <input
            type="text"
            placeholder="Enter note text..."
            value={addText}
            onChange={e => setAddText(e.target.value)}
            className="note-text-input"
            onKeyDown={e => e.key === 'Enter' && handleAdd()}
          />
          <button className="update-btn note-add-btn" onClick={handleAdd}>Add Note</button>
        </div>
        {addStatus && (
          <div className={`note-status ${addStatus.includes('added') ? 'status-ok' : 'status-err'}`}>
            {addStatus}
          </div>
        )}
      </div>

      {loading && <div className="no-data">Loading notes...</div>}
      {!loading && error && <div style={{ color: '#dc3545', padding: '8px' }}>{error}</div>}
      {!loading && !error && sortedDates.length === 0 && (
        <div className="no-data">No notes stored yet.</div>
      )}

      {sortedDates.map(date => (
        <div key={date} className="room-section">
          <h3 className="room-title">{date}</h3>
          <div className="notes-list">
            {Object.entries(notes[date]).map(([id, text]) => (
              <div key={id} className="note-item">
                <div className="note-item-id">ID: {id}</div>
                {editingId === id ? (
                  <div className="note-edit-row">
                    <input
                      type="text"
                      value={editText}
                      onChange={e => setEditText(e.target.value)}
                      className="note-edit-input"
                      onKeyDown={e => {
                        if (e.key === 'Enter') handleEditSave(id);
                        if (e.key === 'Escape') setEditingId(null);
                      }}
                      autoFocus
                    />
                    <button
                      className="update-btn"
                      style={{ width: 'auto', padding: '6px 14px' }}
                      onClick={() => handleEditSave(id)}
                    >Save</button>
                    <button
                      className="refresh-btn"
                      style={{ padding: '6px 14px' }}
                      onClick={() => setEditingId(null)}
                    >Cancel</button>
                  </div>
                ) : (
                  <div className="note-text">{text}</div>
                )}
                {editingId !== id && (
                  <div className="note-actions">
                    <button className="note-edit-btn" onClick={() => { setEditingId(id); setEditText(text); }}>Edit</button>
                    <button className="note-delete-btn" onClick={() => handleDelete(id)}>Delete</button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
};

export default NotesTab;
