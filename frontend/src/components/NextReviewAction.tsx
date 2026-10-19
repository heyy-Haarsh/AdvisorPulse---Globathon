import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import { ConfidencePill, EvidenceBadge } from './EvidenceBadge';
import { PriorityPill } from './PriorityPill';

type Props = {
  investorId: string;
  compact?: boolean;
  onDecided?: () => void;
};

export function NextReviewAction({ investorId, compact = false, onDecided }: Props) {
  const [pack, setPack] = useState<any>(null);
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [approveMsg, setApproveMsg] = useState(false);

  const load = () => {
    setErr('');
    api
      .nextReviewAction(investorId)
      .then(setPack)
      .catch((e) => setErr(String(e)));
  };

  useEffect(() => {
    setPack(null);
    setResult(null);
    load();
  }, [investorId]);

  const decide = async (decision: 'accept' | 'edit' | 'reject') => {
    setBusy(true);
    try {
      const r = await api.decideNextReviewAction(investorId, {
        decision,
        approve_client_message: approveMsg,
        note: decision === 'reject' ? 'Rejected suggested pack' : '',
      });
      setResult(r);
      onDecided?.();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  if (err) return <p className="error">{err}</p>;
  if (!pack) return <p className="muted">Loading next best review action…</p>;

  return (
    <div className="next-action-pack">
      <div className="panel-head" style={{ marginBottom: '0.5rem' }}>
        <h3 style={{ margin: 0 }}>Next Best Review Action</h3>
        <span>
          <PriorityPill priority={pack.priority} />{' '}
          <ConfidencePill confidence={pack.confidence} />
        </span>
      </div>
      <p className="muted" style={{ marginTop: 0 }}>
        {pack.why_escalated}
      </p>

      {!compact && (
        <>
          <p>
            <strong>Suggested:</strong> {pack.suggested_action?.label}
          </p>
          <ul className="factor-list">
            {(pack.verified_facts || []).slice(0, 4).map((f: string) => (
              <li key={f}>
                <span>{f}</span>
              </li>
            ))}
          </ul>
          <p className="muted">Evidence-linked questions</p>
          <ol>
            {(pack.questions || []).map((q: string) => (
              <li key={q}>{q}</li>
            ))}
          </ol>
          {(pack.missing_information || []).length > 0 && (
            <p className="warn">Missing: {(pack.missing_information as string[]).join('; ')}</p>
          )}
          <EvidenceBadge evidence={pack.evidence} />
          <p className="muted" style={{ fontSize: '0.85rem' }}>
            Client message stays <strong>draft</strong> until you approve — no auto-send.
          </p>
          <pre className="draft-msg">{pack.client_message_draft}</pre>
          <label className="muted" style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <input
              type="checkbox"
              checked={approveMsg}
              onChange={(e) => setApproveMsg(e.target.checked)}
            />
            Approve draft for demo send (still not transmitted)
          </label>
        </>
      )}

      {compact && (
        <p>
          <strong>{pack.suggested_action?.key}</strong> — {pack.suggested_action?.label}
        </p>
      )}

      <div className="filters" style={{ marginTop: '0.75rem' }}>
        <button type="button" className="btn" disabled={busy} onClick={() => decide('accept')}>
          Accept action
        </button>
        <button type="button" className="btn soft" disabled={busy} onClick={() => decide('edit')}>
          Edit & accept
        </button>
        <button type="button" className="btn ghost" disabled={busy} onClick={() => decide('reject')}>
          Reject
        </button>
        <Link className="linkish" to={`/meetings/${investorId}`}>
          Meeting prep →
        </Link>
        <Link className="linkish" to={`/clients/${investorId}/overview`}>
          Workspace →
        </Link>
      </div>

      {result && (
        <p className="muted" style={{ marginTop: '0.75rem' }}>
          Recorded <strong>{result.decision}</strong>
          {result.commitment ? ` · commitment ${result.commitment.id?.slice?.(0, 8) || ''}` : ''} ·
          message {result.client_message_status}
        </p>
      )}
    </div>
  );
}
