import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api } from '../api';
import { EvidenceBadge } from '../components/EvidenceBadge';
import { PriorityPill } from '../components/PriorityPill';
import { NextReviewAction } from '../components/NextReviewAction';

export default function MeetingsMemory() {
  const { id: paramId } = useParams();
  const navigate = useNavigate();
  const [investorId, setInvestorId] = useState(paramId || 'DEMO-INV-001');
  const [prep, setPrep] = useState<any>(null);
  const [memory, setMemory] = useState<any>(null);
  const [commitments, setCommitments] = useState<any[]>([]);
  const [noteText, setNoteText] = useState('');
  const [postNotes, setPostNotes] = useState('');
  const [drafts, setDrafts] = useState<any>(null);
  const [err, setErr] = useState('');

  const load = () => {
    setErr('');
    Promise.all([
      api.meetingPrep(investorId),
      api.notes(investorId),
      api.commitments(investorId),
    ])
      .then(([p, n, c]) => {
        setPrep(p);
        setMemory(n);
        setCommitments(c.commitments || []);
      })
      .catch((e) => setErr(String(e)));
  };

  useEffect(() => {
    if (paramId) setInvestorId(paramId);
  }, [paramId]);

  useEffect(() => {
    load();
  }, [investorId]);

  const addNote = async () => {
    if (!noteText.trim()) return;
    await api.addNote(investorId, noteText);
    setNoteText('');
    load();
  };

  const mockTx = async () => {
    await api.mockTranscript(investorId);
    load();
  };

  const confirmExt = async (eid: string) => {
    await api.confirmExtraction(eid, true);
    load();
  };

  const dismissExt = async (eid: string) => {
    await api.dismissExtraction(eid);
    load();
  };

  const draftFollowup = async () => {
    const r = await api.meetingFollowup(investorId, postNotes);
    setDrafts(r);
  };

  const confirmDraft = async (action: string) => {
    await api.addCommitment({ investor_id: investorId, action, status: 'open' });
    setDrafts(null);
    load();
  };

  return (
    <div>
      <div className="page-top">
        <div className="page-header">
          <h1>Meetings & Memory</h1>
          <p>
            Pre-meeting packs, private notes, and <strong>mocked local</strong> transcription —
            extractions need advisor confirmation before they become authoritative.
          </p>
        </div>
      </div>

      <div className="filters">
        <input
          value={investorId}
          onChange={(e) => setInvestorId(e.target.value)}
          placeholder="DEMO-INV-001"
        />
        <button
          type="button"
          className="btn"
          onClick={() => {
            navigate(`/meetings/${investorId}`);
            load();
          }}
        >
          Load
        </button>
        <Link className="linkish" to={`/clients/${investorId}`}>
          Open profile →
        </Link>
      </div>

      {err && <div className="error">{err}</div>}

      <div className="panel">
        <NextReviewAction investorId={investorId} onDecided={load} />
      </div>

      {prep && (
        <div className="panel">
          <h2>
            Pre-meeting pack — {prep.display_name}{' '}
            {prep.priority && <PriorityPill priority={prep.priority.priority} />}
          </h2>
          <EvidenceBadge evidence={prep.evidence} />
          <div className="three-col">
            <div>
              <h3>Agenda</h3>
              <ul>
                {(prep.agenda || []).map((a: string, i: number) => (
                  <li key={i}>{a}</li>
                ))}
              </ul>
            </div>
            <div>
              <h3>Highlights</h3>
              <ul>
                {(prep.structured_highlights || []).slice(0, 5).map((h: any) => (
                  <li key={h.id}>
                    <strong>{h.title}</strong>: {h.summary}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h3>Open questions</h3>
              <ul>
                {(prep.brief?.open_questions || []).map((q: string, i: number) => (
                  <li key={i}>{q}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      <div className="two-col">
        <div className="panel">
          <h2>Advisor notes</h2>
          <textarea value={noteText} onChange={(e) => setNoteText(e.target.value)} placeholder="Private note…" />
          <div className="filters">
            <button type="button" className="btn" onClick={addNote}>
              Save note
            </button>
            <button type="button" className="btn ghost" onClick={mockTx}>
              Mock local transcript
            </button>
          </div>
          <p className="warn">{memory?.transcription_disclaimer}</p>
          <ul className="timeline">
            {(memory?.notes || []).slice().reverse().map((n: any) => (
              <li key={n.note_id}>
                <span className="muted">{String(n.created_at).slice(0, 19)}</span> · {n.source}
                {n.transcript_local === 'true' || n.transcript_local === true ? (
                  <span className="pill hypo">Local/mock</span>
                ) : null}
                <div>{n.note_text}</div>
              </li>
            ))}
          </ul>
        </div>

        <div className="panel">
          <h2>Extractions (confirm before authoritative)</h2>
          {(memory?.extractions || []).filter((e: any) => e.status === 'pending_confirmation').length === 0 && (
            <p className="muted">No pending extractions.</p>
          )}
          {(memory?.extractions || [])
            .filter((e: any) => e.status === 'pending_confirmation')
            .map((e: any) => (
              <div key={e.extraction_id} className="alert-row">
                <div>
                  Topics: {(e.topics || []).join(', ') || '—'}
                  <div className="muted">Commitments: {(e.commitments || []).join('; ')}</div>
                  <EvidenceBadge evidence={e.evidence} />
                </div>
                <div className="filters">
                  <button type="button" className="btn" onClick={() => confirmExt(e.extraction_id)}>
                    Confirm → follow-up
                  </button>
                  <button type="button" className="btn ghost" onClick={() => dismissExt(e.extraction_id)}>
                    Dismiss
                  </button>
                </div>
              </div>
            ))}

          <h2 style={{ marginTop: '1.25rem' }}>Commitments</h2>
          <ul className="timeline">
            {commitments.map((c) => (
              <li key={c.id}>
                <strong>{c.status}</strong> — {c.action}
                {c.due ? <span className="muted"> · due {c.due}</span> : null}
              </li>
            ))}
            {!commitments.length && <li className="muted">No tracked commitments yet.</li>}
          </ul>
        </div>
      </div>

      <div className="panel">
        <h2>Post-meeting follow-through</h2>
        <p className="muted">Draft actions require confirmation before they become commitments.</p>
        <textarea
          value={postNotes}
          onChange={(e) => setPostNotes(e.target.value)}
          placeholder="Meeting outcomes… e.g. agreed to rebalance and review SIP"
        />
        <button type="button" className="btn" onClick={draftFollowup} disabled={!postNotes.trim()}>
          Draft actions
        </button>
        {drafts && (
          <div style={{ marginTop: '0.75rem' }}>
            <EvidenceBadge evidence={drafts.evidence} />
            {(drafts.drafts || []).map((d: any) => (
              <div key={d.draft_id} className="filters">
                <span>{d.action}</span>
                <button type="button" className="btn" onClick={() => confirmDraft(d.action)}>
                  Confirm commitment
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
