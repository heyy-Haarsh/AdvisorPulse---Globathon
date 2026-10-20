import { Link } from 'react-router-dom';

type Props = {
  investorId: string;
  data?: any;
};

/**
 * Retired SIP/contribution simulator tab.
 * Active experience is the book-level Market Shock Simulator.
 */
export function SimulatorTab({ investorId }: Props) {
  return (
    <div className="panel">
      <h2>Simulator moved</h2>
      <p className="muted">
        The SIP/contribution What-if UI has been replaced by the Market Shock Simulator. Per-client
        SIP analysis remains available to Advisor Copilot via validated functions; the interactive
        workspace is now book-level market stress.
      </p>
      <Link className="btn" to={`/what-if/${investorId}`}>
        Open Market Shock Simulator
      </Link>
    </div>
  );
}
