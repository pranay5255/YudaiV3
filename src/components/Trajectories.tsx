import React from 'react';
import { Loader2, Route } from 'lucide-react';

import { Trajectory } from '../types/sessionTypes';

interface TrajectoriesProps {
  trajectories: Trajectory[];
  isLoading: boolean;
  activeSessionId?: string | null;
  onSelect?: (trajectory: Trajectory) => void;
}

const formatDateTime = (value?: string) => {
  if (!value) {
    return '—';
  }

  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
};

const renderSummary = (summary?: Record<string, unknown>) => {
  if (!summary || Object.keys(summary).length === 0) {
    return null;
  }

  const entries = [
    summary.step_count ? { label: 'Steps', value: String(summary.step_count) } : null,
    summary.generated_at ? { label: 'Generated', value: String(summary.generated_at) } : null,
    summary.metadata_model ? { label: 'Model', value: String(summary.metadata_model) } : null,
    summary.metadata_agent ? { label: 'Agent', value: String(summary.metadata_agent) } : null,
    summary.metadata_runtime ? { label: 'Runtime', value: String(summary.metadata_runtime) } : null,
    summary.has_error ? { label: 'Error', value: summary.error_message ? String(summary.error_message) : 'Yes' } : null,
  ].filter(Boolean) as { label: string; value: string }[];

  if (!entries.length) {
    return null;
  }

  return (
    <div className="mt-3 grid gap-2 text-xs text-fg/70 sm:grid-cols-2">
      {entries.map(({ label, value }) => (
        <div
          key={label}
          className="flex items-center justify-between rounded border border-zinc-800/80 bg-zinc-950/40 px-3 py-2"
        >
          <span>{label}</span>
          <span className="font-medium text-fg/80">{value}</span>
        </div>
      ))}
    </div>
  );
};

export const Trajectories: React.FC<TrajectoriesProps> = ({
  trajectories,
  isLoading,
  activeSessionId,
  onSelect,
}) => {
  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center gap-2 text-sm text-fg/70">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading trajectories...
      </div>
    );
  }

  if (!trajectories.length) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 text-center text-sm text-fg/60">
        <Route className="h-6 w-6 text-fg/40" />
        <div>
          <p className="font-medium text-fg">No trajectories yet</p>
          <p className="text-xs text-fg/50">Run the SWE agent to capture your first trajectory.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="grid gap-4">
        {trajectories.map((trajectory) => {
          const isActive = Boolean(
            activeSessionId &&
            (trajectory.session_identifier === activeSessionId || trajectory.session_id.toString() === activeSessionId)
          );

          return (
            <button
              key={trajectory.id}
              type="button"
              onClick={() => onSelect?.(trajectory)}
              className={`w-full rounded-xl border border-zinc-800/80 bg-zinc-900/40 p-4 text-left shadow-sm transition hover:border-primary/40 hover:shadow-primary/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/60 ${
                isActive ? 'border-primary/70 shadow-primary/20' : ''
              }`}
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-fg">{trajectory.session_identifier}</p>
                  {trajectory.issue_number && (
                    <p className="mt-0.5 text-xs text-fg/60">Issue #{trajectory.issue_number}</p>
                  )}
                  {trajectory.repository && (
                    <p className="mt-0.5 text-xs text-fg/60">
                      {trajectory.repository.full_name ||
                        `${trajectory.repository.owner}/${trajectory.repository.name}`}
                    </p>
                  )}
                </div>
                <div className="text-right text-xs text-fg/50">
                  <p>Created</p>
                  <p className="font-medium text-fg/70">{formatDateTime(trajectory.created_at)}</p>
                </div>
              </div>

              {renderSummary(trajectory.summary)}

              <details className="mt-4 text-xs text-fg/70">
                <summary className="cursor-pointer select-none text-fg/80 hover:text-primary/80">
                  View raw trajectory data
                </summary>
                <pre className="mt-2 max-h-64 overflow-auto rounded-lg bg-black/60 p-3 text-[11px] leading-relaxed text-fg/80">
                  {JSON.stringify(trajectory.trajectory_data, null, 2)}
                </pre>
              </details>
            </button>
          );
        })}
      </div>
    </div>
  );
};
