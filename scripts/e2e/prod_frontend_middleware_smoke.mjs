#!/usr/bin/env node
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const FRONTEND_BASE_URL = (process.env.FRONTEND_BASE_URL || 'https://yudai.app').replace(/\/+$/, '');
const BACKEND_BASE_URL = (process.env.BACKEND_BASE_URL || 'https://api.yudai.app').replace(/\/+$/, '');
const SESSION_TOKEN = process.env.E2E_SESSION_TOKEN || process.env.SESSION_TOKEN || '';
const REPO_OWNER = process.env.REPO_OWNER || 'pranay5255';
const REPO_NAME = process.env.REPO_NAME || 'TrustlessLocalAgents';
const REPO_BRANCH = process.env.REPO_BRANCH || 'main';
const REPORT_DIR = process.env.REPORT_DIR || 'logs/e2e';
const TIMEOUT_MS = Number(process.env.E2E_TIMEOUT_MS || '20000');

const rows = [];
let passCount = 0;
let failCount = 0;
let skipCount = 0;
let sessionId = '';
let sandboxId = '';

const mdEscape = (value) => String(value || '')
  .replace(/\n/g, '<br>')
  .replace(/\|/g, '\\|');

const record = (id, status, check, detail = '') => {
  rows.push({ id, status, check, detail });
  if (status === 'PASS') passCount += 1;
  if (status === 'FAIL') failCount += 1;
  if (status === 'SKIP') skipCount += 1;
  console.log(`[${status}] ${id} ${check}${detail ? ` - ${detail}` : ''}`);
};

const withTimeout = async (operation, timeoutMs = TIMEOUT_MS) => {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await operation(controller.signal);
  } finally {
    clearTimeout(timeout);
  }
};

const request = async (baseUrl, route, options = {}) => withTimeout(async (signal) => {
  const headers = new Headers(options.headers || {});
  if (SESSION_TOKEN && options.auth !== false) {
    headers.set('authorization', `Bearer ${SESSION_TOKEN}`);
  }
  if (options.body && !headers.has('content-type')) {
    headers.set('content-type', 'application/json');
  }

  return fetch(`${baseUrl}${route}`, {
    ...options,
    headers,
    signal,
  });
});

const readJson = async (response) => {
  const text = await response.text();
  try {
    return text ? JSON.parse(text) : null;
  } catch {
    return { raw: text };
  }
};

const expectOk = async (id, check, response, detailBuilder) => {
  const body = await readJson(response);
  if (response.ok) {
    record(id, 'PASS', check, detailBuilder ? detailBuilder(body) : JSON.stringify(body).slice(0, 240));
    return body;
  }
  record(id, 'FAIL', check, `HTTP=${response.status} body=${JSON.stringify(body).slice(0, 400)}`);
  return null;
};

const check = async (id, label, fn) => {
  try {
    await fn();
  } catch (error) {
    record(id, 'FAIL', label, error instanceof Error ? error.message : String(error));
  }
};

await check('ENV-001', 'Production smoke token is available', async () => {
  if (!SESSION_TOKEN) {
    throw new Error('Set E2E_SESSION_TOKEN or SESSION_TOKEN to a disposable backend session token');
  }
  record('ENV-001', 'PASS', 'Production smoke token is available', `token_length=${SESSION_TOKEN.length}`);
});

await check('UI-001', 'Landing page route serves the React app', async () => {
  const response = await request(FRONTEND_BASE_URL, '/auth/login', { auth: false });
  const text = await response.text();
  if (!response.ok || !text.includes('id="root"')) {
    throw new Error(`HTTP=${response.status} root_present=${text.includes('id="root"')}`);
  }
  record('UI-001', 'PASS', 'Landing page route serves the React app', `bytes=${text.length}`);
});

await check('AUTH-001', 'Frontend auth rewrite reaches Python REST login', async () => {
  const response = await request(FRONTEND_BASE_URL, '/auth/api/login', { auth: false });
  const body = await expectOk('AUTH-001', 'Frontend auth rewrite reaches Python REST login', response, (json) => (
    `login_url=${String(json?.login_url || '').slice(0, 80)}`
  ));
  if (!body?.login_url || !String(body.login_url).includes('github.com/login/oauth/authorize')) {
    throw new Error('login_url was missing or not a GitHub OAuth URL');
  }
});

await check('AUTH-002', 'Frontend auth rewrite validates session token', async () => {
  const response = await request(FRONTEND_BASE_URL, '/auth/api/user');
  await expectOk('AUTH-002', 'Frontend auth rewrite validates session token', response, (json) => (
    `user=${json?.github_username || 'unknown'}`
  ));
});

await check('MID-001', 'Frontend middleware proxies GitHub repositories', async () => {
  const response = await request(FRONTEND_BASE_URL, '/github/repositories');
  const body = await expectOk('MID-001', 'Frontend middleware proxies GitHub repositories', response, (json) => (
    `repo_count=${Array.isArray(json) ? json.length : 'non-array'}`
  ));
  if (!Array.isArray(body)) {
    throw new Error('Expected repository array');
  }
});

await check('BE-001', 'Backend health endpoint responds', async () => {
  const response = await request(BACKEND_BASE_URL, '/health', { auth: false });
  await expectOk('BE-001', 'Backend health endpoint responds', response);
});

await check('SES-001', 'Frontend middleware creates disposable session', async () => {
  const response = await request(FRONTEND_BASE_URL, '/daifu/sessions', {
    body: JSON.stringify({
      repo_branch: REPO_BRANCH,
      repo_name: REPO_NAME,
      repo_owner: REPO_OWNER,
    }),
    method: 'POST',
  });
  const body = await expectOk('SES-001', 'Frontend middleware creates disposable session', response, (json) => (
    `session_id=${json?.session_id || 'missing'} sandbox_id=${json?.sandbox_id || 'none'}`
  ));
  sessionId = body?.session_id || '';
  sandboxId = body?.sandbox_id || '';
  if (!sessionId) {
    throw new Error('session_id missing');
  }
});

await check('AI-001', 'Vercel AI stream route returns AI SDK UI stream', async () => {
  if (!sessionId) {
    record('AI-001', 'SKIP', 'Vercel AI stream route returns AI SDK UI stream', 'session creation failed');
    return;
  }
  const response = await request(FRONTEND_BASE_URL, `/ai/sessions/${encodeURIComponent(sessionId)}/stream`, {
    body: JSON.stringify({
      context_card_ids: [],
      messageId: 'prod_smoke_user',
      messages: [{
        id: 'prod_smoke_user',
        parts: [{ text: 'Reply with a short production smoke acknowledgement.', type: 'text' }],
        role: 'user',
      }],
      repository: { branch: REPO_BRANCH, name: REPO_NAME, owner: REPO_OWNER },
      session_id: sessionId,
      trigger: 'prod-smoke',
    }),
    method: 'POST',
  });
  const text = await response.text();
  const streamHeader = response.headers.get('x-vercel-ai-ui-message-stream');
  if (!response.ok || streamHeader !== 'v1' || !text.includes('text')) {
    throw new Error(`HTTP=${response.status} stream_header=${streamHeader} body_preview=${text.slice(0, 240)}`);
  }
  record('AI-001', 'PASS', 'Vercel AI stream route returns AI SDK UI stream', `bytes=${text.length}`);
});

await check('RT-001', 'Realtime SSE bridge opens backend WebSocket after auth', async () => {
  if (!sessionId) {
    record('RT-001', 'SKIP', 'Realtime SSE bridge opens backend WebSocket after auth', 'session creation failed');
    return;
  }
  await withTimeout(async (signal) => {
    const response = await fetch(
      `${FRONTEND_BASE_URL}/realtime/sessions/${encodeURIComponent(sessionId)}/events`,
      {
        headers: { authorization: `Bearer ${SESSION_TOKEN}` },
        signal,
      }
    );
    if (!response.ok || !response.body) {
      throw new Error(`HTTP=${response.status}`);
    }
    const reader = response.body.getReader();
    const { value } = await reader.read();
    await reader.cancel();
    reader.releaseLock();
    const chunk = new TextDecoder().decode(value);
    record('RT-001', 'PASS', 'Realtime SSE bridge opens backend WebSocket after auth', chunk.slice(0, 240));
  }, 12000);
});

await check('CLN-001', 'Disposable sandbox cleanup', async () => {
  if (!sandboxId) {
    record('CLN-001', 'SKIP', 'Disposable sandbox cleanup', 'session response did not include sandbox_id');
    return;
  }
  const response = await request(FRONTEND_BASE_URL, `/controller/sandboxes/${encodeURIComponent(sandboxId)}`, {
    method: 'DELETE',
  });
  if (response.status === 204) {
    record('CLN-001', 'PASS', 'Disposable sandbox cleanup', `sandbox_id=${sandboxId}`);
    return;
  }
  const body = await response.text();
  record('CLN-001', 'FAIL', 'Disposable sandbox cleanup', `HTTP=${response.status} body=${body.slice(0, 240)}`);
});

await mkdir(REPORT_DIR, { recursive: true });
const timestamp = new Date().toISOString().replace(/[-:]/g, '').replace(/\..+/, 'Z');
const reportPath = path.join(REPORT_DIR, `prod_frontend_middleware_report_${timestamp}.md`);
const report = [
  '# Production Frontend Middleware Smoke Report',
  '',
  `- Timestamp: ${new Date().toISOString()}`,
  `- Frontend: \`${FRONTEND_BASE_URL}\``,
  `- Backend: \`${BACKEND_BASE_URL}\``,
  `- Repo: \`${REPO_OWNER}/${REPO_NAME}@${REPO_BRANCH}\``,
  '',
  '## Summary',
  '',
  `- PASS: ${passCount}`,
  `- FAIL: ${failCount}`,
  `- SKIP: ${skipCount}`,
  '',
  '## Results',
  '',
  '| ID | Status | Check | Details |',
  '|---|---|---|---|',
  ...rows.map((row) => `| \`${row.id}\` | **${row.status}** | ${mdEscape(row.check)} | ${mdEscape(row.detail)} |`),
  '',
].join('\n');

await writeFile(reportPath, report, 'utf8');
console.log(`Report written: ${reportPath}`);
console.log(`PASS=${passCount} FAIL=${failCount} SKIP=${skipCount}`);

if (failCount > 0) {
  process.exit(1);
}
