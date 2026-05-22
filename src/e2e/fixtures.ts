import { expect, test as base } from '@playwright/test';
import type { APIResponse, Page } from '@playwright/test';

type UserConfig = {
  displayName: string;
  email: string;
  id: string;
  username: string;
};

type RepositoryConfig = {
  branch: string;
  name: string;
  owner: string;
};

export type RealSiteConfig = {
  apiBaseURL: string;
  baseURL: string;
  repository: RepositoryConfig;
  sessionToken: string;
  user: UserConfig;
};

type AuthenticatedPageApi = {
  get: (path: string) => Promise<APIResponse>;
  post: (path: string, body?: unknown) => Promise<APIResponse>;
  put: (path: string, body?: unknown) => Promise<APIResponse>;
};

type RealSiteFixtures = {
  authApi: AuthenticatedPageApi;
  e2eConfig: RealSiteConfig;
};

const REQUIRED_ENV = [
  'E2E_SESSION_TOKEN',
  'E2E_USER_ID',
  'E2E_USERNAME',
  'E2E_USER_EMAIL',
  'E2E_REPO_OWNER',
  'E2E_REPO_NAME',
  'E2E_REPO_BRANCH',
] as const;

function requiredEnv(name: (typeof REQUIRED_ENV)[number]): string {
  const value = process.env[name]?.trim();
  if (!value) {
    throw new Error(`Missing required real-site E2E environment variable: ${name}`);
  }
  return value;
}

function loadConfig(): RealSiteConfig {
  for (const name of REQUIRED_ENV) {
    requiredEnv(name);
  }

  const baseURL = (process.env.PLAYWRIGHT_BASE_URL || 'https://yudai.app').replace(/\/+$/, '');

  return {
    apiBaseURL: (process.env.PLAYWRIGHT_API_BASE_URL || baseURL).replace(/\/+$/, ''),
    baseURL,
    repository: {
      branch: requiredEnv('E2E_REPO_BRANCH'),
      name: requiredEnv('E2E_REPO_NAME'),
      owner: requiredEnv('E2E_REPO_OWNER'),
    },
    sessionToken: requiredEnv('E2E_SESSION_TOKEN'),
    user: {
      displayName: process.env.E2E_USER_DISPLAY_NAME?.trim() || requiredEnv('E2E_USERNAME'),
      email: requiredEnv('E2E_USER_EMAIL'),
      id: requiredEnv('E2E_USER_ID'),
      username: requiredEnv('E2E_USERNAME'),
    },
  };
}

function absoluteUrl(config: RealSiteConfig, path: string): string {
  return new URL(path, `${config.apiBaseURL}/`).href;
}

function authHeaders(config: RealSiteConfig, hasBody = false): Record<string, string> {
  return {
    ...(hasBody ? { 'Content-Type': 'application/json' } : {}),
    Authorization: `Bearer ${config.sessionToken}`,
  };
}

function buildAuthSuccessUrl(config: RealSiteConfig): string {
  const url = new URL('/auth/success', `${config.baseURL}/`);
  url.searchParams.set('session_token', config.sessionToken);
  url.searchParams.set('user_id', config.user.id);
  url.searchParams.set('username', config.user.username);
  url.searchParams.set('name', config.user.displayName);
  url.searchParams.set('email', config.user.email);
  return url.href;
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

async function isVisible(locator: ReturnType<Page['locator']>): Promise<boolean> {
  try {
    return await locator.isVisible({ timeout: 1_000 });
  } catch {
    return false;
  }
}

export const test = base.extend<RealSiteFixtures>({
  authApi: async ({ page, e2eConfig }, use) => {
    await use({
      get: (path) => page.request.get(absoluteUrl(e2eConfig, path), {
        headers: authHeaders(e2eConfig),
      }),
      post: (path, body) => page.request.post(absoluteUrl(e2eConfig, path), {
        data: body,
        headers: authHeaders(e2eConfig, body !== undefined),
      }),
      put: (path, body) => page.request.put(absoluteUrl(e2eConfig, path), {
        data: body,
        headers: authHeaders(e2eConfig, body !== undefined),
      }),
    });
  },
  e2eConfig: async ({}, use) => {
    await use(loadConfig());
  },
});

export { expect };

export async function authenticateViaCallback(
  page: Page,
  config: RealSiteConfig
): Promise<void> {
  try {
    await page.goto(buildAuthSuccessUrl(config), { waitUntil: 'domcontentloaded' });
    await page.waitForURL((url) => url.pathname === '/', { timeout: 20_000 });
  } catch {
    await page.goto('about:blank').catch(() => undefined);
    throw new Error('Real-site E2E authentication callback did not land on the app root.');
  }
}

export async function selectConfiguredRepository(
  page: Page,
  config: RealSiteConfig
): Promise<void> {
  const fullName = `${config.repository.owner}/${config.repository.name}`;
  const selectedRepository = page.getByRole('button', {
    name: new RegExp(`^Selected repository ${escapeRegExp(fullName)}$`, 'i'),
  });

  if (!(await isVisible(selectedRepository))) {
    await page.getByRole('button', { name: /selected repository/i }).click();
    await page.getByPlaceholder('Search repositories').fill(fullName);
    await page.getByRole('button', {
      name: new RegExp(escapeRegExp(fullName), 'i'),
    }).first().click();
  }

  await expect(selectedRepository).toBeVisible();
  await expect(async () => {
    await page.getByLabel('Branch').selectOption(config.repository.branch);
  }).toPass({ timeout: 15_000 });
}

export async function responseJson<T>(
  response: APIResponse,
  label: string
): Promise<T> {
  try {
    return await response.json() as T;
  } catch {
    throw new Error(`${label} did not return JSON.`);
  }
}
