import { API_BASE } from '../config/api';
import type {
  ApiSchema,
  CreateSessionRequest,
  ExecutionRequest,
  ExecutionResponse,
  ExecutionStatus,
  GitHubBranch,
  GitHubRepository,
  Runtime,
  Session,
  SessionContext,
  ChatMessage,
} from '../types/apiContract';

type QueryValue = string | number | boolean | null | undefined;

type RequestOptions = {
  body?: unknown;
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
  pathParams?: Record<string, string | number>;
  query?: Record<string, QueryValue>;
  token?: string | null;
};

export type ContractRepository = GitHubRepository;
export type ContractBranch = GitHubBranch;
export type ContractSession = Session;
export type ContractSessionContext = SessionContext;
export type ContractChatMessage = ChatMessage;
export type ContractExecutionResponse = ExecutionResponse;
export type ContractExecutionStatus = ExecutionStatus;
export type ContractRuntime = Runtime;
export type ContractIssue = ApiSchema<'UserIssueResponse'>;
export type ContractGitHubIssue = ApiSchema<'GitHubIssueResponse'>;
export type ContractTrajectory = ApiSchema<'TrajectorySummaryResponse'>;
export type ContractContextCard = ApiSchema<'ContextCardResponse'>;
export type ContractUserQuestion = ApiSchema<'UserQuestionResponse'>;
export type ContractAnswerQuestionRequest = ApiSchema<'AnswerQuestionRequest'>;
export type ContractAnswerQuestionResponse = ApiSchema<'AnswerQuestionResponse'>;

export class AgentApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'AgentApiError';
    this.status = status;
  }
}

function replacePathParams(
  path: string,
  params: Record<string, string | number> = {}
): string {
  return Object.entries(params).reduce((nextPath, [key, value]) => (
    nextPath.replace(`{${key}}`, encodeURIComponent(String(value)))
  ), path);
}

function appendQuery(path: string, query: Record<string, QueryValue> = {}): string {
  const searchParams = new URLSearchParams();

  Object.entries(query).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== '') {
      searchParams.set(key, String(value));
    }
  });

  const queryString = searchParams.toString();
  return queryString ? `${path}?${queryString}` : path;
}

function buildContractUrl(
  path: string,
  params?: Record<string, string | number>,
  query?: Record<string, QueryValue>
): string {
  return `${API_BASE}${appendQuery(replacePathParams(path, params), query)}`;
}

function getHeaders(token?: string | null, hasBody = false): HeadersInit {
  const headers: HeadersInit = {};

  if (hasBody) {
    headers['Content-Type'] = 'application/json';
  }

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  return headers;
}

function getErrorMessage(payload: unknown, fallback: string): string {
  if (!payload || typeof payload !== 'object') {
    return fallback;
  }

  const record = payload as Record<string, unknown>;
  const detail = record.detail;

  if (typeof detail === 'string') {
    return detail;
  }

  if (detail && typeof detail === 'object') {
    const detailRecord = detail as Record<string, unknown>;
    if (typeof detailRecord.message === 'string') {
      return detailRecord.message;
    }
    if (typeof detailRecord.detail === 'string') {
      return detailRecord.detail;
    }
  }

  if (typeof record.message === 'string') {
    return record.message;
  }

  return fallback;
}

async function requestJson<TResponse>(
  path: string,
  options: RequestOptions = {}
): Promise<TResponse> {
  const method = options.method || 'GET';
  const hasBody = options.body !== undefined;
  const response = await fetch(
    buildContractUrl(path, options.pathParams, options.query),
    {
      method,
      headers: getHeaders(options.token, hasBody),
      body: hasBody ? JSON.stringify(options.body) : undefined,
    }
  );

  if (!response.ok) {
    let payload: unknown = null;

    try {
      payload = await response.json();
    } catch {
      payload = null;
    }

    throw new AgentApiError(
      response.status,
      getErrorMessage(payload, `Request failed with status ${response.status}`)
    );
  }

  if (response.status === 204) {
    return undefined as TResponse;
  }

  return response.json() as Promise<TResponse>;
}

export const agentApi = {
  listRepositories(token?: string | null): Promise<ContractRepository[]> {
    return requestJson<ContractRepository[]>('/daifu/github/repositories', {
      token,
    });
  },

  listBranches(
    owner: string,
    repo: string,
    token?: string | null
  ): Promise<ContractBranch[]> {
    return requestJson<ContractBranch[]>(
      '/daifu/github/repositories/{owner}/{repo}/branches',
      {
        pathParams: { owner, repo },
        token,
      }
    );
  },

  listRepositoryIssues(
    owner: string,
    repo: string,
    token?: string | null,
    limit = 20
  ): Promise<ContractGitHubIssue[]> {
    return requestJson<ContractGitHubIssue[]>(
      '/daifu/github/repositories/{owner}/{repo}/issues',
      {
        pathParams: { owner, repo },
        query: { limit },
        token,
      }
    );
  },

  createSession(
    body: CreateSessionRequest,
    token?: string | null
  ): Promise<ContractSession> {
    return requestJson<ContractSession>('/daifu/sessions', {
      body,
      method: 'POST',
      token,
    });
  },

  getSessionContext(
    sessionId: string,
    token?: string | null
  ): Promise<ContractSessionContext> {
    return requestJson<ContractSessionContext>('/daifu/sessions/{session_id}', {
      pathParams: { session_id: sessionId },
      token,
    });
  },

  answerQuestion(
    sessionId: string,
    questionId: string,
    body: ContractAnswerQuestionRequest,
    token?: string | null
  ): Promise<ContractAnswerQuestionResponse> {
    return requestJson<ContractAnswerQuestionResponse>(
      '/daifu/sessions/{session_id}/questions/{question_id}/answer',
      {
        body,
        method: 'POST',
        pathParams: { session_id: sessionId, question_id: questionId },
        token,
      }
    );
  },

  listContextCards(
    sessionId: string,
    token?: string | null
  ): Promise<ContractContextCard[]> {
    return requestJson<ContractContextCard[]>(
      '/daifu/sessions/{session_id}/context-cards',
      {
        pathParams: { session_id: sessionId },
        token,
      }
    );
  },

  listSessionIssues(
    sessionId: string,
    token?: string | null,
    limit = 20
  ): Promise<ContractIssue[]> {
    return requestJson<ContractIssue[]>('/daifu/sessions/{session_id}/issues', {
      pathParams: { session_id: sessionId },
      query: { limit },
      token,
    });
  },

  createIssuePreview(
    sessionId: string,
    body: Record<string, unknown>,
    token?: string | null
  ): Promise<ApiSchema<'IssueCreationResponse'>> {
    return requestJson<ApiSchema<'IssueCreationResponse'>>(
      '/daifu/sessions/{session_id}/issues/create-with-context',
      {
        body,
        method: 'POST',
        pathParams: { session_id: sessionId },
        token,
      }
    );
  },

  getExecutionStatus(
    sessionId: string,
    token?: string | null
  ): Promise<ContractExecutionStatus> {
    return requestJson<ContractExecutionStatus>(
      '/daifu/sessions/{session_id}/execution',
      {
        pathParams: { session_id: sessionId },
        token,
      }
    );
  },

  startExecution(
    sessionId: string,
    body: ExecutionRequest,
    token?: string | null
  ): Promise<ContractExecutionResponse> {
    return requestJson<ContractExecutionResponse>(
      '/daifu/sessions/{session_id}/execution',
      {
        body,
        method: 'POST',
        pathParams: { session_id: sessionId },
        token,
      }
    );
  },

  cancelExecution(
    sessionId: string,
    token?: string | null
  ): Promise<ApiSchema<'CancelExecutionResponse'>> {
    return requestJson<ApiSchema<'CancelExecutionResponse'>>(
      '/daifu/sessions/{session_id}/execution/cancel',
      {
        method: 'POST',
        pathParams: { session_id: sessionId },
        token,
      }
    );
  },

  ensureRuntime(
    sessionId: string,
    body: ApiSchema<'RuntimeEnsureRequest'>,
    token?: string | null
  ): Promise<ContractRuntime> {
    return requestJson<ContractRuntime>(
      '/controller/sessions/{session_id}/runtime',
      {
        body,
        method: 'POST',
        pathParams: { session_id: sessionId },
        token,
      }
    );
  },

  listTrajectories(
    sessionId: string,
    token?: string | null
  ): Promise<ContractTrajectory[]> {
    return requestJson<ContractTrajectory[]>(
      '/daifu/sessions/{session_id}/trajectories',
      {
        pathParams: { session_id: sessionId },
        token,
      }
    );
  },
};
