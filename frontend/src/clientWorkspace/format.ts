export function formatInr(value: number | null | undefined, opts?: { lakhs?: boolean }): string {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return 'N/A';
  const n = Number(value);
  if (opts?.lakhs) {
    return `₹${(n / 1e5).toFixed(1)}L`;
  }
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(n);
}

export function formatPct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return 'N/A';
  return `${Number(value).toFixed(digits)}%`;
}

export function formatPp(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return 'N/A';
  const n = Number(value);
  return `${n >= 0 ? '+' : ''}${n.toFixed(digits)} pp`;
}

export const WORKSPACE_TABS = [
  { id: 'overview', label: 'Overview', path: 'overview' },
  { id: 'evidence', label: 'Evidence & Summary', path: 'evidence' },
  { id: 'portfolio', label: 'Portfolio & Drift', path: 'portfolio' },
  { id: 'meetings', label: 'Meetings & Advice', path: 'meetings' },
  { id: 'simulator', label: 'What-if Simulator', path: 'simulator' },
  { id: 'review-actions', label: 'Review Actions', path: 'review-actions' },
] as const;

export type WorkspaceTabId = (typeof WORKSPACE_TABS)[number]['id'];

export function normalizeTab(tab?: string): WorkspaceTabId {
  const t = (tab || 'overview').toLowerCase();
  const hit = WORKSPACE_TABS.find((x) => x.path === t || x.id === t);
  return hit?.id ?? 'overview';
}

export const EVIDENCE_CATEGORY_MAP: { id: string; title: string; match: string[] }[] = [
  { id: 'identity', title: 'Client identity and objectives', match: ['identity'] },
  { id: 'goal_position', title: 'Goal position', match: ['goal_position'] },
  { id: 'portfolio_allocation', title: 'Portfolio allocation', match: ['portfolio_allocation'] },
  { id: 'performance', title: 'Performance versus benchmark', match: ['performance'] },
  { id: 'gap_drivers', title: 'Goal deviation and contributing factors', match: ['gap_drivers'] },
  { id: 'advice_outcomes', title: 'Advice-to-outcome', match: ['advice_outcomes'] },
  { id: 'drift_signals', title: 'Hidden drift signals', match: ['drift_signals'] },
  { id: 'commitments', title: 'Outstanding commitments', match: ['commitments'] },
  { id: 'data_quality', title: 'Data quality', match: ['data_quality'] },
  { id: 'recommended_actions', title: 'Recommended review actions', match: ['recommended_actions'] },
];
