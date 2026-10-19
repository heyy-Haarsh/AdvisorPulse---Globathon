import type { EvidenceEnvelope } from '../api';

export function ConfidencePill({ confidence }: { confidence?: string }) {
  const c = confidence || 'Limited';
  return (
    <span className={`pill conf ${c}`} data-c={c} title="Evidence confidence">
      {c}
    </span>
  );
}

export function EvidenceBadge({ evidence }: { evidence?: EvidenceEnvelope | null }) {
  if (!evidence) return null;
  return (
    <details className="evidence-box">
      <summary>
        <ConfidencePill confidence={evidence.confidence} />
        <span className="muted"> {evidence.claim?.slice(0, 80)}</span>
        {evidence.is_hypothetical ? <span className="pill hypo">Hypothetical</span> : null}
      </summary>
      {evidence.evidence?.length ? (
        <ul className="evidence-list">
          {evidence.evidence.map((e, i) => (
            <li key={i}>
              <strong>{e.source}</strong>
              {e.as_of ? <span className="muted"> · {e.as_of}</span> : null}
              {e.detail ? <div className="muted">{e.detail}</div> : null}
              {e.record_ids?.length ? (
                <div className="muted">Records: {e.record_ids.slice(0, 4).join(', ')}</div>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
      {evidence.missing_data?.length ? (
        <p className="warn">Missing: {evidence.missing_data.join(', ')}</p>
      ) : null}
      {evidence.limitations?.length ? (
        <p className="muted">Limitations: {evidence.limitations.slice(0, 2).join(' ')}</p>
      ) : null}
      {evidence.next_steps?.length ? (
        <p className="muted">Next: {evidence.next_steps.join('; ')}</p>
      ) : null}
    </details>
  );
}
