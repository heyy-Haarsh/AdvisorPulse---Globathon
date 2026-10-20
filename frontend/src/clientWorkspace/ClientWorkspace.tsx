import { useEffect, useState } from 'react';
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom';
import { api } from '../api';
import { PriorityPill } from '../components/PriorityPill';
import { ConfidencePill } from '../components/EvidenceBadge';
import { CopilotChatPanel } from '../components/CopilotChatPanel';
import {
  WORKSPACE_TABS,
  formatInr,
  formatPct,
  formatPp,
  normalizeTab,
  type WorkspaceTabId,
} from './format';
import { OverviewTab } from './tabs/OverviewTab';
import { EvidenceTab } from './tabs/EvidenceTab';
import { PortfolioTab } from './tabs/PortfolioTab';
import { MeetingsAdviceTab } from './tabs/MeetingsAdviceTab';
import { ReviewActionsTab } from './tabs/ReviewActionsTab';

type Props = {
  /** When embedded inside Clients directory layout */
  investorId: string;
};

export function ClientWorkspace({ investorId }: Props) {
  const { tab: tabParam } = useParams();
  const navigate = useNavigate();
  const tab = normalizeTab(tabParam);

  const [data, setData] = useState<any>(null);
  const [timeline, setTimeline] = useState<any>(null);
  const [crosscheck, setCrosscheck] = useState<any>(null);
  const [pack, setPack] = useState<any>(null);
  const [commitments, setCommitments] = useState<any[]>([]);
  const [notes, setNotes] = useState<any>(null);
  const [err, setErr] = useState('');
  const [loading, setLoading] = useState(true);
  const [copilotOpen, setCopilotOpen] = useState(false);

  const load = async () => {
    setLoading(true);
    setErr('');
    try {
      const [inv, tl, cc, p, c, n] = await Promise.all([
        api.investor(investorId),
        api.timeline(investorId),
        api.performanceCrosscheck(investorId),
        api.nextReviewAction(investorId),
        api.commitments(investorId),
        api.notes(investorId),
      ]);
      setData(inv);
      setTimeline(tl);
      setCrosscheck(cc);
      setPack(p);
      setCommitments(c.commitments || []);
      setNotes(n);
    } catch (e) {
      setErr(String(e));
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    setCopilotOpen(false);
  }, [investorId]);

  // Ensure URL has a tab segment
  if (!tabParam) {
    return <Navigate to={`/clients/${investorId}/overview`} replace />;
  }

  const goTab = (id: WorkspaceTabId) => {
    navigate(`/clients/${investorId}/${id}`);
  };

  const onDrift = async (alertId: string, status: string) => {
    await api.setDriftStatus(alertId, status);
    setData(await api.investor(investorId));
  };

  const onFeedback = async (ref: string, action: string) => {
    await api.feedback({
      investor_id: investorId,
      insight_ref: ref,
      action,
      correction: action === 'correct' ? 'Advisor corrected insight' : undefined,
    });
    setTimeline(await api.timeline(investorId));
  };

  if (loading) return <div className="loading">Loading client workspace…</div>;
  if (err) return <div className="error">{err}</div>;
  if (!data) return <div className="muted">Client not found.</div>;

  const inv = data.snapshot.investor;
  const gp = data.snapshot.goal_progress;
  const perf = data.snapshot.performance;
  const openDrift = (data.drift?.alerts || []).filter(
    (a: any) => !a.status || a.status === 'open' || a.status === 'confirmed',
  ).length;
  const pv = data.snapshot.portfolio_value;
  const goalDev = gp?.deviation_pct_vs_expected;
  const active = perf?.active_return_pct;

  return (
    <div className="client-workspace">
      <header className="ws-header">
        <div className="ws-identity">
          <h1>{inv.display_name}</h1>
          <p className="muted">
            {inv.investor_id}
            {inv.city ? ` · ${inv.city}` : ''}
            {inv.is_demo || data.snapshot.is_demo ? ' · Synthetic demo data' : ''}
          </p>
          <div className="ws-badges">
            <PriorityPill priority={data.priority.priority} />
            <span className="ws-score">Score {data.priority.score}</span>
            <ConfidencePill confidence={data.priority.confidence} />
          </div>
        </div>
        <div className="ws-header-actions">
          <button type="button" className="btn" onClick={() => setCopilotOpen(true)}>
            Ask Copilot
          </button>
          <button
            type="button"
            className="btn soft"
            onClick={() => goTab('review-actions')}
          >
            Review action
          </button>
          <Link className="btn ghost" to={`/meetings/${investorId}`}>
            Meeting prep
          </Link>
          <Link className="btn soft" to={`/meeting-intel/${investorId}/history`}>
            Meeting Intelligence
          </Link>
        </div>
      </header>

      <div className="ws-kpi-strip" aria-label="Key metrics">
        <div className="ws-kpi">
          <div className="label">Portfolio value</div>
          <div className="value">{formatInr(pv, { lakhs: true })}</div>
          <div className="muted">Market value (DEMO)</div>
        </div>
        <div className="ws-kpi">
          <div className="label">Goal vs expected path</div>
          <div
            className="value"
            style={{
              color:
                goalDev == null
                  ? undefined
                  : goalDev < 0
                    ? 'var(--critical)'
                    : 'var(--ontrack)',
            }}
          >
            {formatPct(goalDev)}
          </div>
          <div className="muted">Deviation % vs path</div>
        </div>
        <div className="ws-kpi">
          <div className="label">Active return</div>
          <div className="value">{formatPp(active)}</div>
          <div className="muted">Portfolio − benchmark (pp)</div>
        </div>
        <div className="ws-kpi">
          <div className="label">Open drift alerts</div>
          <div className="value">{openDrift}</div>
          <div className="muted">Confirm / dismiss / resolve</div>
        </div>
      </div>

      <nav className="ws-tabs" role="tablist" aria-label="Client workspace">
        {WORKSPACE_TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            className={`ws-tab ${tab === t.id ? 'active' : ''}`}
            onClick={() => goTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <div className="ws-tab-panel" role="tabpanel">
        {tab === 'overview' && (
          <OverviewTab
            investorId={investorId}
            data={data}
            pack={pack}
            timeline={timeline}
            commitments={commitments}
          />
        )}
        {tab === 'evidence' && <EvidenceTab investorId={investorId} data={data} />}
        {tab === 'portfolio' && (
          <PortfolioTab data={data} crosscheck={crosscheck} onDrift={onDrift} />
        )}
        {tab === 'meetings' && (
          <MeetingsAdviceTab
            investorId={investorId}
            data={data}
            timeline={timeline}
            commitments={commitments}
            notes={notes}
            onFeedback={onFeedback}
          />
        )}
        {tab === 'review-actions' && (
          <ReviewActionsTab
            investorId={investorId}
            timeline={timeline}
            onDecided={async () => {
              await load();
            }}
          />
        )}
      </div>

      <CopilotChatPanel
        investorId={investorId}
        displayName={inv.display_name}
        tab={tab}
        open={copilotOpen}
        onOpenChange={setCopilotOpen}
      />
    </div>
  );
}
