export const EXECUTION_OBJECTIVE_MAX_CHARS = 10000;

const TRUNCATION_SUFFIX = '...';

export type ExecutionObjectiveIssue = {
  body?: string | null;
  branch?: string | null;
  html_url?: string | null;
  notes?: Array<string | false | null | undefined>;
  number?: number | string | null;
  repository?: string | null;
  repoName?: string | null;
  repoOwner?: string | null;
  title?: string | null;
  url?: string | null;
};

export function capExecutionObjective(
  objective: string,
  maxChars = EXECUTION_OBJECTIVE_MAX_CHARS
): string {
  const trimmed = objective.trim();
  if (trimmed.length <= maxChars) {
    return trimmed;
  }
  if (maxChars <= TRUNCATION_SUFFIX.length) {
    return trimmed.slice(0, Math.max(maxChars, 0));
  }

  return `${trimmed.slice(0, maxChars - TRUNCATION_SUFFIX.length).trimEnd()}${TRUNCATION_SUFFIX}`;
}

export function buildExecutionObjective(
  issue: ExecutionObjectiveIssue,
  maxChars = EXECUTION_OBJECTIVE_MAX_CHARS
): string {
  const issueNumber = normalizeString(issue.number);
  const issueUrl = normalizeString(issue.url) || normalizeString(issue.html_url);
  const title = normalizeString(issue.title);
  const issueLabel = issueNumber ? `#${issueNumber}` : issueUrl || 'selected issue';
  const summary = title
    ? `Resolve GitHub issue ${issueLabel}: ${title}`
    : `Resolve GitHub issue ${issueLabel}`;

  const sections = [summary];
  if (issueUrl) {
    sections.push(`GitHub issue URL: ${issueUrl}`);
  }

  const repository = getRepositoryLabel(issue);
  if (repository) {
    sections.push(`Repository: ${repository}`);
  }

  const notes = issue.notes
    ?.map((note) => normalizeString(note))
    .filter((note): note is string => Boolean(note)) || [];
  sections.push(...notes);

  const body = compactText(issue.body || '');
  if (body) {
    const fixedWithoutBody = [...sections, 'Issue details:\n'].join('\n\n');
    const bodyBudget = maxChars - fixedWithoutBody.length;
    if (bodyBudget > 0) {
      sections.push(`Issue details:\n${capExecutionObjective(body, bodyBudget)}`);
    } else {
      return capExecutionObjective(sections.join('\n\n'), maxChars);
    }
  }

  return capExecutionObjective(sections.join('\n\n'), maxChars);
}

function getRepositoryLabel(issue: ExecutionObjectiveIssue): string {
  const repository = normalizeString(issue.repository);
  const branch = normalizeString(issue.branch);
  const owner = normalizeString(issue.repoOwner);
  const name = normalizeString(issue.repoName);
  const repoLabel = repository || (owner && name ? `${owner}/${name}` : '');

  return repoLabel && branch ? `${repoLabel}@${branch}` : repoLabel;
}

function normalizeString(value: unknown): string {
  if (value === null || value === undefined || value === false) {
    return '';
  }

  return String(value).trim();
}

function compactText(value: string): string {
  return value.split(/\s+/).filter(Boolean).join(' ');
}
