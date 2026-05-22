import { expect, test as base } from '@playwright/test';
import type { APIRequestContext, APIResponse, Page, Response } from '@playwright/test';

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
  mockRepositoryApi: boolean;
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
    mockRepositoryApi: process.env.E2E_MOCK_REPOSITORY_API === '1',
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

function createAuthenticatedApi(
  request: APIRequestContext,
  config: RealSiteConfig
): AuthenticatedPageApi {
  return {
    get: (path) => request.get(absoluteUrl(config, path), {
      headers: authHeaders(config),
    }),
    post: (path, body) => request.post(absoluteUrl(config, path), {
      data: body,
      headers: authHeaders(config, body !== undefined),
    }),
    put: (path, body) => request.put(absoluteUrl(config, path), {
      data: body,
      headers: authHeaders(config, body !== undefined),
    }),
  };
}

export const test = base.extend<RealSiteFixtures>({
  authApi: async ({ request, e2eConfig }, use) => {
    await use(createAuthenticatedApi(request, e2eConfig));
  },
  e2eConfig: async ({}, use) => {
    await use(loadConfig());
  },
});

export { expect };

export async function installRepositoryApiMocks(
  page: Page,
  config: RealSiteConfig
): Promise<void> {
  if (!config.mockRepositoryApi) {
    return;
  }

  const fullName = `${config.repository.owner}/${config.repository.name}`;
  const now = new Date().toISOString();

  await page.route('**/daifu/github/repositories**', async (route) => {
    if (route.request().method() !== 'GET') {
      await route.fallback();
      return;
    }

    const path = new URL(route.request().url()).pathname;

    if (path === '/daifu/github/repositories') {
      await route.fulfill({
        contentType: 'application/json',
        json: [{
          clone_url: `https://github.com/${fullName}.git`,
          created_at: now,
          default_branch: config.repository.branch,
          description: 'Real-site E2E repository fixture',
          forks_count: 0,
          full_name: fullName,
          html_url: `https://github.com/${fullName}`,
          id: 9_000_001,
          language: 'TypeScript',
          name: config.repository.name,
          open_issues_count: 0,
          owner: {
            avatar_url: null,
            html_url: `https://github.com/${config.repository.owner}`,
            id: 9_000_002,
            login: config.repository.owner,
          },
          private: false,
          pushed_at: now,
          stargazers_count: 0,
          updated_at: now,
        }],
      });
      return;
    }

    if (path.endsWith(`/${config.repository.owner}/${config.repository.name}/branches`)) {
      await route.fulfill({
        contentType: 'application/json',
        json: [{
          commit: {
            sha: 'e2e-fixture',
            url: `https://api.github.com/repos/${fullName}/commits/e2e-fixture`,
          },
          name: config.repository.branch,
          protected: false,
        }],
      });
      return;
    }

    if (path.endsWith(`/${config.repository.owner}/${config.repository.name}/issues`)) {
      await route.fulfill({
        contentType: 'application/json',
        json: [],
      });
      return;
    }

    await route.fallback();
  });
}

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
  response: APIResponse | Response,
  label: string
): Promise<T> {
  try {
    return await response.json() as T;
  } catch {
    throw new Error(`${label} did not return JSON.`);
  }
}
