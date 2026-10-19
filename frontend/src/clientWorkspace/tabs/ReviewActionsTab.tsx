import { NextReviewAction } from '../../components/NextReviewAction';

type Props = {
  investorId: string;
  onDecided: () => void;
  timeline: any;
};

export function ReviewActionsTab({ investorId, onDecided, timeline }: Props) {
  const related = (timeline?.events || [])
    .filter(
      (e: any) =>
        String(e.title || '').toLowerCase().includes('review') ||
        String(e.type || '').includes('decision') ||
        String(e.ref || '').includes('next_action'),
    )
    .slice(-12)
    .reverse();

  return (
    <div className="ws-review">
      <section className="panel">
        <h2>Recommended review action</h2>
        <p className="muted">
          Full Next Best Review Action workflow. Client messages remain <strong>Draft — Not Sent</strong>{' '}
          until you explicitly approve. No automatic send.
        </p>
        <NextReviewAction investorId={investorId} onDecided={onDecided} />
      </section>

      <section className="panel">
        <h2>Decision history</h2>
        <p className="muted">From timeline / attention decisions related to review actions.</p>
        <ul className="timeline">
          {related.map((e: any, i: number) => (
            <li key={i}>
              <span className="muted">{e.ts}</span> · <strong>{e.type}</strong> — {e.title}
            </li>
          ))}
        </ul>
        {!related.length && (
          <p className="muted">No review-action decisions recorded yet for this client.</p>
        )}
      </section>
    </div>
  );
}
