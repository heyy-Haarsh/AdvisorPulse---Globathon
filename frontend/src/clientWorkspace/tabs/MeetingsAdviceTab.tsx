import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ConfidencePill, EvidenceBadge } from '../../components/EvidenceBadge';

type Props = {
  investorId: string;
  data: any;
  timeline: any;
  commitments: any[];
  notes: any;
  onFeedback: (ref: string, action: string) => Promise<void>;
};

export function MeetingsAdviceTab({
  investorId,
  data,
  timeline,
  commitments,
  notes,
  onFeedback,
}: Props) {
  const [sub, setSub] = useState<'meetings' | 'advice' | 'commitments'>('meetings');
  const [commitFilter, setCommitFilter] = useState('all');
  const [expandedNote, setExpandedNote] = useState<string | null>(null);
  const [showRawFeedback, setShowRawFeedback] = useState(false);

  const noteList = notes?.notes || [];
  const adviceItems = data.advice_outcomes?.items || [];

  const filteredCommitments = useMemo(() => {
    return commitments.filter((c) => {
      if (commitFilter === 'pending') return ['open', 'pending', 'confirmed'].includes(c.status);
      if (commitFilter === 'completed') return c.status === 'done' || c.status === 'completed';
      if (commitFilter === 'overdue') {
        if (!c.due) return false;
        return new Date(c.due) < new Date() && !['done', 'completed'].includes(c.status);
      }
      return true;
    });
  }, [commitments, commitFilter]);

  const feedbackEvents = (timeline?.events || []).filter(
    (e: any) => e.type === 'advisor_feedback' || e.type === 'attention_decision',
  );
  const otherEvents = (timeline?.events || []).filter(
    (e: any) => e.type !== 'advisor_feedback',
  );

  return (
    <div>
      <div className="ws-subnav" role="tablist">
        <button
          type="button"
          className={`btn ${sub === 'meetings' ? '' : 'ghost'}`}
          onClick={() => setSub('meetings')}
        >
          Meetings & Minutes
        </button>
        <button
          type="button"
          className={`btn ${sub === 'advice' ? '' : 'ghost'}`}
          onClick={() => setSub('advice')}
        >
          Advice & Outcomes
        </button>
        <button
          type="button"
          className={`btn ${sub === 'commitments' ? '' : 'ghost'}`}
          onClick={() => setSub('commitments')}
        >
          Commitments & Feedback
        </button>
        <Link className="btn soft" to={`/meetings/${investorId}`}>
          Full meeting prep →
        </Link>
        <Link className="btn" to={`/meeting-intel/${investorId}/history`}>
          Meeting Intelligence →
        </Link>
      </div>

      {sub === 'meetings' && (
        <section className="panel">
          <h2>Meetings & minutes</h2>
          <p className="muted">
            Showing recorded notes and mock transcriptions. No fabricated meetings are invented when
            history is empty. Structured meeting creation beyond notes is available on Meetings &amp;
            Memory.
          </p>
          {[...noteList].reverse().map((n: any) => (
            <article key={n.note_id || n.id} className="ws-meeting-card">
              <button
                type="button"
                className="ws-drift-head"
                onClick={() =>
                  setExpandedNote(
                    expandedNote === (n.note_id || n.id) ? null : n.note_id || n.id,
                  )
                }
              >
                <div>
                  <strong>{n.source === 'mock_transcript' ? 'Mock transcript' : 'Advisor note'}</strong>
                  <div className="muted">{n.created_at || n.ts || 'Date N/A'}</div>
                </div>
                <span className="muted">{(n.note_text || '').slice(0, 48)}…</span>
              </button>
              {expandedNote === (n.note_id || n.id) && (
                <div className="ws-drift-body">
                  <h3>Minutes / notes</h3>
                  <pre className="draft-msg">{n.note_text}</pre>
                  <p className="muted">
                    Status: {n.confirmed ? 'advisor-confirmed extract path' : 'raw note / pending extract'}
                  </p>
                  <Link className="linkish" to={`/meetings/${investorId}`}>
                    Open meeting workspace →
                  </Link>
                </div>
              )}
            </article>
          ))}
          {!noteList.length && (
            <p className="muted">
              No meeting notes on record for this client yet.{' '}
              <Link to={`/meetings/${investorId}`}>Add notes / mock transcript →</Link>
            </p>
          )}

          <h3>Recent relationship events</h3>
          <ul className="timeline">
            {otherEvents.slice(-10).reverse().map((e: any, i: number) => (
              <li key={i}>
                <span className="muted">{e.ts}</span> · <strong>{e.type}</strong> — {e.title}
              </li>
            ))}
          </ul>
        </section>
      )}

      {sub === 'advice' && (
        <section className="panel">
          <h2>Advice & outcomes</h2>
          <p className="muted">
            Outcomes are deterministic comparisons where data exists. Temporal proximity is not
            treated as causality.
          </p>
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Recommendation</th>
                <th>Intended</th>
                <th>Observed / status</th>
                <th>Evidence</th>
              </tr>
            </thead>
            <tbody>
              {adviceItems.map((item: any) => (
                <tr key={item.advice_id}>
                  <td>{item.advice_date || 'N/A'}</td>
                  <td>{item.recommendation}</td>
                  <td className="muted">{item.intended_outcome || '—'}</td>
                  <td>{item.outcome_status}</td>
                  <td>
                    <ConfidencePill confidence={item.evidence?.confidence} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!adviceItems.length && <p className="muted">No advice records for this client.</p>}
          <EvidenceBadge evidence={data.advice_outcomes?.summary} />
        </section>
      )}

      {sub === 'commitments' && (
        <section className="panel">
          <h2>Commitments</h2>
          <div className="filters">
            <select value={commitFilter} onChange={(e) => setCommitFilter(e.target.value)}>
              <option value="all">All</option>
              <option value="pending">Pending</option>
              <option value="overdue">Overdue</option>
              <option value="completed">Completed</option>
            </select>
          </div>
          {filteredCommitments.map((c: any) => (
            <div key={c.id || c.action} className="ws-commit-row">
              <strong>{c.action}</strong>
              <div className="muted">
                Owner: {c.owner || 'advisor'} · {c.status}
                {c.due ? ` · due ${c.due}` : ''} · source {c.source || '—'}
              </div>
            </div>
          ))}
          {!filteredCommitments.length && <p className="muted">No commitments in this filter.</p>}

          <h3>Advisor feedback history</h3>
          <button
            type="button"
            className="btn ghost"
            onClick={() => setShowRawFeedback((v) => !v)}
          >
            {showRawFeedback ? 'Hide' : 'Show'} activity log ({feedbackEvents.length})
          </button>
          {showRawFeedback && (
            <ul className="timeline">
              {feedbackEvents
                .slice()
                .reverse()
                .map((e: any, i: number) => (
                  <li key={i}>
                    <span className="muted">{e.ts}</span> · {e.title}
                    {e.ref && (
                      <span className="filters" style={{ display: 'inline-flex', marginLeft: 8 }}>
                        <button
                          type="button"
                          className="btn ghost"
                          onClick={() => onFeedback(e.ref, 'confirm')}
                        >
                          Confirm
                        </button>
                        <button
                          type="button"
                          className="btn ghost"
                          onClick={() => onFeedback(e.ref, 'dismiss')}
                        >
                          Dismiss
                        </button>
                      </span>
                    )}
                  </li>
                ))}
            </ul>
          )}
          <p className="muted">{timeline?.improvement_note}</p>
        </section>
      )}
    </div>
  );
}
