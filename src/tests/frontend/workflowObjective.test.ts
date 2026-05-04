import { describe, expect, it } from 'vitest';
import {
  EXECUTION_OBJECTIVE_MAX_CHARS,
  buildExecutionObjective,
  capExecutionObjective,
} from '@/utils/workflowObjective';

describe('workflow objective helpers', () => {
  it('caps long manual objectives at the execution request limit', () => {
    const objective = capExecutionObjective(`Fix auth\n${'x'.repeat(12000)}`);

    expect(objective.length).toBeLessThanOrEqual(EXECUTION_OBJECTIVE_MAX_CHARS);
    expect(objective).toContain('Fix auth');
    expect(objective.endsWith('...')).toBe(true);
  });

  it('keeps issue metadata and truncates the issue body excerpt', () => {
    const objective = buildExecutionObjective({
      body: `Keep this first sentence. ${'body '.repeat(400)}`,
      branch: 'main',
      html_url: 'https://github.com/octocat/yudaiv3/issues/191',
      number: 191,
      repository: 'octocat/yudaiv3',
      title: 'Stabilize workflow state',
    }, 280);

    expect(objective.length).toBeLessThanOrEqual(280);
    expect(objective).toContain('Resolve GitHub issue #191: Stabilize workflow state');
    expect(objective).toContain('GitHub issue URL: https://github.com/octocat/yudaiv3/issues/191');
    expect(objective).toContain('Repository: octocat/yudaiv3@main');
    expect(objective).toContain('Issue details:\nKeep this first sentence.');
    expect(objective.endsWith('...')).toBe(true);
  });
});
