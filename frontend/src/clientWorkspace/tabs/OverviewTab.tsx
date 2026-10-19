import { Link } from 'react-router-dom';
import { ConfidencePill, EvidenceBadge } from '../../components/EvidenceBadge';
import { PriorityPill } from '../../components/PriorityPill';

type Props = {
  investorId: string;
  data: any;
  pack: any;
  timeline: any;
  commitments: any[];
};

export function OverviewTab({ investorId, data, pack, timeline, commitments }: Props) {
  const pri = data.priority;
  const alerts = (data.drift?.alerts || []).filter((a: any) => a.status === 'open' || !a.status);
  const openCommitments = commitments.filter((c) =>
    ['open', 'pending', 'confirmed'].includes(c.status),
  );
  const events = (timeline?.events || []).slice(-8).reverse();

  return (
    <div className="ws-overview">
      <div className="ws-overview-main">
        <section className="panel">
          <div className="panel-head">
            <h2>Client attention summary</h2>
            <PriorityPill priority={pri.priority} />
          </div>
          <p>
            Score <strong>{pri.score}</strong> · <ConfidencePill confidence={pri.confidence} />
          </p>
          <p>{pri.priority_reason}</p>
          <ul className="factor-list">
            {(pri.factors || []).slice(0, 4).map((f: any) => (
              <li key={f.name}>
                <span>
                  {f.name}
                  <div className="muted">{f.detail}</div>
                </span>
                <span className="pts">{f.points}</span>
              </li>
            ))}
          </ul>
          <EvidenceBadge evidence={pri.evidence} />
          <Link className="btn soft" to={`/clients/${investorId}/evidence`}>
            Inspect supporting evidence →
          </Link>
        </section>

        <section className="panel ws-action-preview">
          <div className="panel-head">
            <h2>Next Best Review Action</h2>
            <span className="muted">Preview</span>
          </div>
          {pack ? (
            <>
              <p>
                <strong>{pack.suggested_action?.label}</strong>
              </p>
              <p className="muted">{pack.why_escalated}</p>
              <ul className="factor-list">
                {(pack.verified_facts || []).slice(0, 3).map((f: string) => (
                  <li key={f}>
                    <span>{f}</span>
                  </li>
                ))}
              </ul>
              <p className="muted">Priority questions</p>
              <ol>
                {(pack.questions || []).slice(0, 3).map((q: string) => (
                  <li key={q}>{q}</li>
                ))}
              </ol>
              <Link className="btn" to={`/clients/${investorId}/review-actions`}>
                Open full Review Actions →
              </Link>
            </>
          ) : (
            <p className="muted">Loading review action preview…</p>
          )}
        </section>

        <section className="panel">
          <div className="panel-head">
            <h2>Important alerts</h2>
            <Link className="linkish" to={`/clients/${investorId}/portfolio`}>
              View all →
            </Link>
          </div>
          {alerts.slice(0, 4).map((a: any) => (
            <div key={a.alert_id} className="ws-alert-mini">
              <strong>{a.title}</strong>
              <span className="muted">
                {' '}
                · {a.severity}
                {a.is_distress ? '' : ' · not distress'}
              </span>
              <div className="muted">{a.evidence?.claim}</div>
              <ConfidencePill confidence={a.evidence?.confidence} />
            </div>
          ))}
          {!alerts.length && <p className="muted">No open drift alerts.</p>}
        </section>
      </div>

      <aside className="ws-overview-side">
        <section className="panel">
          <h2>Upcoming commitments</h2>
          {openCommitments.slice(0, 6).map((c: any) => (
            <div key={c.id || c.action} className="ws-commit-row">
              <strong>{c.action}</strong>
              <div className="muted">
                {c.status}
                {c.due ? ` · due ${c.due}` : ''}
              </div>
            </div>
          ))}
          {!openCommitments.length && <p className="muted">No open commitments on record.</p>}
          <Link className="linkish" to={`/clients/${investorId}/meetings`}>
            Meetings & Advice →
          </Link>
        </section>

        <section className="panel">
          <div className="panel-head">
            <h2>Recent activity</h2>
            <Link className="linkish" to={`/clients/${investorId}/meetings`}>
              Full history →
            </Link>
          </div>
          <ul className="timeline">
            {events.map((e: any, i: number) => (
              <li key={i}>
                <span className="muted">{e.ts}</span> · <strong>{e.type}</strong> — {e.title}
              </li>
            ))}
          </ul>
          {!events.length && <p className="muted">No recent timeline events.</p>}
        </section>
      </aside>
    </div>
  );
}
