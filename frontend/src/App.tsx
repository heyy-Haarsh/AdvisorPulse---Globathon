import { NavLink, Route, Routes, Navigate, useParams } from 'react-router-dom';
import Overview from './pages/Overview';
import Clients from './pages/Clients';
import MeetingsMemory from './pages/MeetingsMemory';
import Insights from './pages/Insights';
import AlertQualityLab from './pages/AlertQualityLab';
import Settings from './pages/Settings';
import MeetingIntelligence from './pages/MeetingIntelligence';
import WhatIfSimulator from './pages/WhatIfSimulator';
import AttentionEngine from './pages/AttentionEngine';

function RedirectClient() {
  const { id } = useParams();
  return <Navigate to={`/clients/${id}`} replace />;
}

function RedirectMeetings() {
  const { id } = useParams();
  return <Navigate to={`/meetings/${id}`} replace />;
}

function Icon({ d }: { d: string }) {
  return (
    <svg className="nav-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d={d} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

const ICONS = {
  overview: 'M4 10.5 12 4l8 6.5V20a1 1 0 0 1-1 1h-5v-6H10v6H5a1 1 0 0 1-1-1v-9.5z',
  attention:
    'M12 3a9 9 0 1 1-6.36 2.64M12 7v5l3 2M4.93 4.93l1.41 1.41M2 12h2M4.93 19.07l1.41-1.41',
  clients: 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75',
  meetings: 'M8 7V3m8 4V3M4 11h16M6 5h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z',
  intel:
    'M12 3a3 3 0 0 1 3 3v1h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2h2V6a3 3 0 0 1 3-3zm-1 8h2v5h-2v-5zm1-6a1 1 0 0 0-1 1v1h2V6a1 1 0 0 0-1-1z',
  insights: 'M4 19V5m0 14h16M8 15v4m4-8v8m4-12v12',
  whatif:
    'M4 19V5m4 10 3-8 3 5 3-10 3 13M3 19h18',
  settings: 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9c.3.6.9 1 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z',
};

export default function App() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-row">
          <div className="brand-mark" aria-hidden>
            <span />
          </div>
          <div className="brand">
            Advisor <span>Pulse</span>
          </div>
        </div>

        <div className="sidebar-user">
          <div className="avatar">AP</div>
          <div>
            <div className="hello">Welcome back,</div>
            <div className="name">Demo Advisor</div>
          </div>
        </div>

        <nav className="nav">
          <NavLink to="/" end>
            <Icon d={ICONS.overview} />
            Overview
          </NavLink>
          <NavLink to="/attention-engine">
            <Icon d={ICONS.attention} />
            Attention Engine
          </NavLink>
          <NavLink to="/clients">
            <Icon d={ICONS.clients} />
            Clients
          </NavLink>
          <NavLink
            to="/what-if"
            className={({ isActive }) => (isActive ? 'active' : undefined)}
          >
            <Icon d={ICONS.whatif} />
            Market Scenarios
          </NavLink>
          <NavLink to="/meetings">
            <Icon d={ICONS.meetings} />
            Meetings & Memory
          </NavLink>
          <NavLink to="/meeting-intel">
            <Icon d={ICONS.intel} />
            Meeting Intelligence
          </NavLink>
          <NavLink to="/insights">
            <Icon d={ICONS.insights} />
            Insights
            <span className="nav-badge">3</span>
          </NavLink>
          <NavLink to="/settings">
            <Icon d={ICONS.settings} />
            Settings
          </NavLink>
        </nav>

        <div className="sidebar-foot">
          <div className="demo-badge">
            DEMO DATA ONLY — synthetic portfolio universe. Not investment advice. Transcription is
            mocked/local only.
          </div>
          <button type="button" className="logout-btn" title="Demo session">
            <span>Demo session</span>
            <span>→</span>
          </button>
        </div>
      </aside>

      <main className="main">
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/attention-engine" element={<AttentionEngine />} />
          <Route path="/clients" element={<Clients />} />
          <Route path="/clients/:id" element={<Clients />} />
          <Route path="/clients/:id/:tab" element={<Clients />} />
          <Route path="/what-if" element={<WhatIfSimulator />} />
          <Route path="/what-if/:id" element={<WhatIfSimulator />} />
          <Route path="/market-shock" element={<Navigate to="/what-if" replace />} />
          <Route path="/market-shock/:id" element={<WhatIfSimulator />} />
          <Route path="/meetings" element={<MeetingsMemory />} />
          <Route path="/meetings/:id" element={<MeetingsMemory />} />
          <Route path="/meeting-intel" element={<Navigate to="/meeting-intel/DEMO-INV-001/history" replace />} />
          <Route path="/meeting-intel/:clientId/history" element={<MeetingIntelligence />} />
          <Route path="/meeting-intel/:clientId/:meetingId/:stage" element={<MeetingIntelligence />} />
          <Route path="/meeting-intel/:clientId" element={<MeetingIntelligence />} />
          <Route path="/insights" element={<Insights />} />
          <Route path="/insights/alert-quality" element={<AlertQualityLab />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/attention" element={<Navigate to="/attention-engine" replace />} />
          <Route path="/investor/:id" element={<RedirectClient />} />
          <Route path="/meeting/:id" element={<RedirectMeetings />} />
          <Route path="/notes/:id" element={<RedirectMeetings />} />
        </Routes>
      </main>
    </div>
  );
}
