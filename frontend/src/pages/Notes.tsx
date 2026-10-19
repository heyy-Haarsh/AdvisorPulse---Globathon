import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../api';

export default function Notes() {
  const { id = 'DEMO-INV-001' } = useParams();
  const [notes, setNotes] = useState<any[]>([]);
  const [text, setText] = useState('');
  const [editId, setEditId] = useState<string | null>(null);
  const [editText, setEditText] = useState('');
  const [msg, setMsg] = useState('');

  const load = () => api.notes(id).then((r) => setNotes(r.notes));

  useEffect(() => {
    load().catch(console.error);
  }, [id]);

  const add = async () => {
    if (!text.trim()) return;
    await api.addNote(id, text.trim());
    setText('');
    await load();
  };

  const saveEdit = async () => {
    if (!editId) return;
    try {
      await api.updateNote(editId, editText);
      setEditId(null);
      await load();
    } catch {
      setMsg('Seed CSV notes are read-only; only runtime notes can be edited.');
    }
  };

  const mockTx = async () => {
    const r = await api.mockTranscript(id);
    setMsg(
      `Transcription mode: ${r.processing_mode}. ${r.security_note}`
    );
    await load();
  };

  return (
    <div>
      <div className="page-header">
        <h1>Advisor Notes</h1>
        <p>
          Capture advisor knowledge. Transcription demo uses a <strong>mocked local</strong> path —
          no audio is uploaded to an external model.
        </p>
      </div>

      {msg && (
        <div className="warn" style={{ marginBottom: '1rem' }}>
          {msg}
        </div>
      )}

      <div className="panel">
        <h2>Add note</h2>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Meeting observations, client preferences, follow-ups…"
        />
        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.6rem' }}>
          <button className="btn" onClick={add}>
            Save note
          </button>
          <button className="btn ghost" onClick={mockTx}>
            Mock local transcription
          </button>
        </div>
      </div>

      <div className="panel">
        <h2>Notes for {id}</h2>
        {notes.length === 0 && <p className="muted">No notes yet.</p>}
        {notes.map((n) => (
          <div
            key={n.note_id}
            style={{
              borderBottom: '1px solid var(--border)',
              padding: '0.85rem 0',
            }}
          >
            <div className="muted">
              {n.created_at} · {n.author} · source={n.source}
              {n.transcript_local === 'true' || n.transcript_local === true
                ? ' · local/mock transcript'
                : ''}
            </div>
            {editId === n.note_id ? (
              <>
                <textarea value={editText} onChange={(e) => setEditText(e.target.value)} />
                <button className="btn" onClick={saveEdit}>
                  Update
                </button>
              </>
            ) : (
              <>
                <p style={{ margin: '0.35rem 0' }}>{n.note_text}</p>
                {String(n.note_id).includes('RT') || String(n.note_id).includes('TX') ? (
                  <button
                    className="linkish"
                    onClick={() => {
                      setEditId(n.note_id);
                      setEditText(n.note_text);
                    }}
                  >
                    Edit
                  </button>
                ) : (
                  <span className="muted">Seed note (read-only)</span>
                )}
              </>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
