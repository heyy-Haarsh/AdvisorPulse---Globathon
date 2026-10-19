import type { Priority } from '../api';

export function PriorityPill({ priority }: { priority: Priority | string }) {
  return (
    <span className="pill" data-p={priority}>
      {priority}
    </span>
  );
}
