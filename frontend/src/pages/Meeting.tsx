import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api';

export default function Meeting() {
  const { id = 'DEMO-INV-001' } = useParams();
  const [brief, setBrief] = useState<any>(null);
  const [err, setErr] = useState('');

  useEffect(() => {
    setBrief(null);
    api.brief(id).then(setBrief).catch((e) => setErr(String(e)));
  }, [id]);

  if (err) return <div className="error">{err}</div>;
  if (!brief) return <div className="loading">Preparing meeting brief…</div>;

  return (
    <div>
      <div className="page-header">
        <h1>{brief.headline}</h1>
        <p>
          Concise prep from structured data and prior advice — human stays in control.{' '}
          <Link to={`/investor/${id}`}>Open full summary →</Link>
        </p>
      </div>

      <div className="panel">
        <h2>One-paragraph context</h2>
        <p>{brief.one_paragraph}</p>
      </div>

      <div className="three-col">
        <div className="panel">
          <h2>Open questions</h2>
          <ul>
            {brief.open_questions.map((q: string) => (
              <li key={q}>{q}</li>
            ))}
          </ul>
        </div>
        <div className="panel">
          <h2>Outstanding commitments</h2>
          <ul>
            {brief.outstanding_commitments.map((c: any, i: number) => (
              <li key={i}>
                <strong>{c.status}</strong>: {c.item}
                {c.due ? ` (due ${c.due})` : ''}
              </li>
            ))}
          </ul>
        </div>
        <div className="panel">
          <h2>Discussion points</h2>
          <ul>
            {brief.suggested_discussion_points.map((d: string) => (
              <li key={d}>{d}</li>
            ))}
          </ul>
        </div>
      </div>

      <div className="panel">
        <h2>Recent developments</h2>
        <ul>
          {(brief.recent_developments || []).map((d: any, i: number) => (
            <li key={i}>
              [{d.type}] {d.detail}
            </li>
          ))}
        </ul>
        <p className="muted">Limitations: {(brief.limitations || []).join(' ')}</p>
      </div>
    </div>
  );
}
