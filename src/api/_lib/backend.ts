export type AuthenticatedUser = {
  id: number;
  github_username: string;
  github_id?: string | null;
  display_name?: string | null;
  email?: string | null;
  avatar_url?: string | null;
};

export type AuthenticatedRequest = {
  sessionToken: string;
  user: AuthenticatedUser;
};

const DEFAULT_BACKEND_BASE_URL = 'https://api.yudai.app';

export const getBackendBaseUrl = (): string => (
  (
    process.env.YUDAI_BACKEND_BASE_URL ||
    process.env.VITE_AUTH_API_BASE_URL ||
    process.env.VITE_API_BASE_URL ||
    DEFAULT_BACKEND_BASE_URL
  ).replace(/\/+$/, '')
);

export const getInternalMiddlewareSecret = (): string => (
  process.env.YUDAI_INTERNAL_MIDDLEWARE_SECRET ||
  process.env.INTERNAL_MIDDLEWARE_SECRET ||
  ''
);

export const jsonResponse = (status: number, body: unknown): Response => (
  new Response(JSON.stringify(body), {
    status,
    headers: {
      'content-type': 'application/json',
    },
  })
);

export const extractBearerToken = (request: Request): string | null => {
  const authorization = request.headers.get('authorization') || '';
  const match = authorization.match(/^Bearer\s+(.+)$/i);
  return match ? match[1].trim() : null;
};

export const requireAuthenticatedUser = async (
  request: Request
): Promise<AuthenticatedRequest | Response> => {
  const sessionToken = extractBearerToken(request);
  if (!sessionToken) {
    return jsonResponse(401, { detail: 'Missing bearer token' });
  }

  const response = await fetch(`${getBackendBaseUrl()}/auth/api/user`, {
    headers: {
      Authorization: `Bearer ${sessionToken}`,
    },
  });

  if (!response.ok) {
    return jsonResponse(response.status === 401 ? 401 : 502, {
      detail: response.status === 401 ? 'Invalid bearer token' : 'Auth validation failed',
    });
  }

  const user = await response.json() as AuthenticatedUser;
  return { sessionToken, user };
};

export const isAuthResult = (
  value: AuthenticatedRequest | Response
): value is AuthenticatedRequest => !(value instanceof Response);

const appendSearch = (path: string, sourceUrl: string): string => {
  const search = new URL(sourceUrl).search;
  return search ? `${path}${search}` : path;
};

export const buildBackendHttpHeaders = (
  auth: AuthenticatedRequest,
  request: Request,
  hasBody: boolean
): Headers => {
  const headers = new Headers();
  const internalSecret = getInternalMiddlewareSecret();

  headers.set('accept', request.headers.get('accept') || 'application/json');
  if (hasBody) {
    headers.set('content-type', request.headers.get('content-type') || 'application/json');
  }

  if (internalSecret) {
    headers.set('x-yudai-internal-secret', internalSecret);
    headers.set('x-yudai-user-id', String(auth.user.id));
  } else {
    headers.set('authorization', `Bearer ${auth.sessionToken}`);
  }

  return headers;
};

export const proxyBackendRequest = async (
  request: Request,
  backendPath?: string
): Promise<Response> => {
  const auth = await requireAuthenticatedUser(request);
  if (!isAuthResult(auth)) {
    return auth;
  }

  const url = new URL(request.url);
  const path = backendPath || url.pathname.replace(/^\/api\/proxy/, '') || '/';
  const target = `${getBackendBaseUrl()}${appendSearch(path, request.url)}`;
  const method = request.method.toUpperCase();
  const hasBody = !['GET', 'HEAD'].includes(method);
  const response = await fetch(target, {
    method,
    headers: buildBackendHttpHeaders(auth, request, hasBody),
    body: hasBody ? request.body : undefined,
    duplex: hasBody ? 'half' : undefined,
  } as RequestInit & { duplex?: 'half' });

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: response.headers,
  });
};

export const getRequiredInternalSecretResponse = (): Response | null => {
  if (getInternalMiddlewareSecret()) {
    return null;
  }

  return jsonResponse(500, {
    detail: 'YUDAI_INTERNAL_MIDDLEWARE_SECRET is required for middleware-to-backend realtime access',
  });
};
