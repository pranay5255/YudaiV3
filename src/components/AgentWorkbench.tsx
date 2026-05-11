import { useChat } from '@ai-sdk/react';
import {
  DefaultChatTransport,
  getToolName,
  isToolUIPart,
} from 'ai';
import type {
  UIMessage,
  UIMessagePart,
  UITools,
} from 'ai';
import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity,
  AlertCircle,
  ArrowRight,
  Bot,
  ChevronDown,
  CheckCircle2,
  CircleDot,
  Clock3,
  Code2,
  Database,
  ExternalLink,
  FolderGit2,
  GitBranch,
  Github,
  GitPullRequestArrow,
  Layers3,
  Loader2,
  LogOut,
  MessageSquareText,
  Play,
  RefreshCw,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  Square,
  TerminalSquare,
  XCircle,
  Zap,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { API, buildApiUrl } from '../config/api';
import {
  agentApi,
  AgentApiError,
  ContractBranch,
  ContractChatMessage,
  ContractContextCard,
  ContractExecutionStatus,
  ContractGitHubIssue,
  ContractIssue,
  ContractRepository,
  ContractRuntime,
  ContractSession,
  ContractSessionContext,
  ContractTrajectory,
  ContractUserQuestion,
} from '../services/agentApi';
import { UserQuestionPrompt } from './UserQuestionPrompt';
import type { AgentQuestionInfo } from '../types/sessionTypes';
import { capExecutionObjective } from '../utils/workflowObjective';

type WorkspaceView = 'chat' | 'context' | 'execution' | 'issues';
type ExecutionMode = 'architect' | 'tester' | 'coder';
type NoticeTone = 'info' | 'success' | 'error';
type RuntimeProvisionStatus = 'failed' | 'not_provisioned' | 'provisioning' | 'running';

type Notice = {
  id: string;
  message: string;
  tone: NoticeTone;
};

type YudaiChatMessageMetadata = {
  createdAt?: string;
  error?: boolean;
  errorMessage?: string | null;
  modelUsed?: string | null;
  tokens?: number;
};

type YudaiStatusData = string | {
  level?: NoticeTone | string;
  message?: string;
  status?: string;
  tone?: NoticeTone | string;
};

type YudaiActionData = {
  action_type: string;
  label: string;
  issue_description?: string | null;
  issue_title?: string | null;
  labels?: string[] | null;
};

type YudaiAgentQuestionData = Partial<AgentQuestionInfo> & {
  multi_select?: boolean;
  prompt?: string;
  question_text?: string;
};

type YudaiDataParts = {
  action: YudaiActionData;
  'agent-question': YudaiAgentQuestionData;
  status: YudaiStatusData;
};

type YudaiChatMessage = UIMessage<YudaiChatMessageMetadata, YudaiDataParts>;
type YudaiMessagePart = UIMessagePart<YudaiDataParts, UITools>;

type SessionStats = {
  contextCount: number;
  issueCount: number;
  messageCount: number;
  tokenCount: number;
};

const WORKSPACE_TABS: Array<{
  icon: LucideIcon;
  id: WorkspaceView;
  label: string;
}> = [
  { id: 'chat', label: 'Chat', icon: MessageSquareText },
  { id: 'context', label: 'Context', icon: Layers3 },
  { id: 'execution', label: 'Runs', icon: TerminalSquare },
  { id: 'issues', label: 'Issues', icon: GitPullRequestArrow },
];

const EXECUTION_MODES: Array<{
  description: string;
  icon: LucideIcon;
  id: ExecutionMode;
  label: string;
  role: string;
}> = [
  {
    description: 'Frames the adversarial objective and selects the next legal move.',
    icon: Sparkles,
    id: 'architect',
    label: 'Architect',
    role: 'Orchestrator',
  },
  {
    description: 'Validates evidence, regressions, and test boundaries before edits.',
    icon: ShieldCheck,
    id: 'tester',
    label: 'Tester',
    role: 'Validator',
  },
  {
    description: 'Applies constrained code changes after the lifecycle gate opens.',
    icon: Code2,
    id: 'coder',
    label: 'Coder',
    role: 'Worker',
  },
];

function cx(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(' ');
}

function getRepositoryOwner(repository: ContractRepository): string {
  return repository.owner?.login || repository.full_name.split('/')[0] || '';
}

function getDefaultBranch(repository: ContractRepository): string {
  return repository.default_branch || 'main';
}

function getRepositoryRuntimeUrl(repository: ContractRepository): string {
  return repository.clone_url
    || repository.html_url
    || `https://github.com/${repository.full_name}.git`;
}

function getErrorText(error: unknown, fallback: string): string {
  if (error instanceof AgentApiError || error instanceof Error) {
    return error.message || fallback;
  }

  return fallback;
}

function formatCompactNumber(value?: number | null): string {
  if (value === null || value === undefined) {
    return '0';
  }

  return new Intl.NumberFormat('en-US', {
    maximumFractionDigits: value > 999 ? 1 : 0,
    notation: value > 999 ? 'compact' : 'standard',
  }).format(value);
}

function formatDateTime(value?: string | null): string {
  if (!value) {
    return 'Not started';
  }

  return new Intl.DateTimeFormat('en-US', {
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    month: 'short',
  }).format(new Date(value));
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function toOptionalString(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value : undefined;
}

function toStringArray(value: unknown): string[] | undefined {
  if (!Array.isArray(value)) {
    return undefined;
  }

  return value.filter((item): item is string => typeof item === 'string');
}

function toAiMessage(message: ContractChatMessage): YudaiChatMessage {
  const role = message.role === 'user' || message.role === 'system'
    ? message.role
    : 'assistant';
  const parts: YudaiChatMessage['parts'] = [
    {
      text: message.message_text,
      type: 'text',
    },
  ];

  if (Array.isArray(message.actions)) {
    message.actions.forEach((action, index) => {
      parts.push({
        data: {
          action_type: action.action_type,
          issue_description: action.issue_description,
          issue_title: action.issue_title,
          label: action.label,
          labels: action.labels,
        },
        id: `${message.message_id}_action_${index}`,
        type: 'data-action',
      });
    });
  }

  return {
    id: message.message_id,
    metadata: {
      createdAt: message.created_at,
      error: Boolean(message.error_message),
      errorMessage: message.error_message,
      modelUsed: message.model_used,
      tokens: message.tokens,
    },
    parts,
    role,
  };
}

function toAgentQuestionInfo(question: ContractUserQuestion): AgentQuestionInfo {
  return {
    multi_select: question.multi_select,
    options: question.options || [],
    question_id: question.question_id,
    question_text: question.prompt,
  };
}

function getGatheringState(session: ContractSession | null): string | null {
  const metadata = session?.mode_metadata;
  if (!metadata || typeof metadata !== 'object') {
    return null;
  }

  const value = (metadata as Record<string, unknown>).gathering_state;
  return typeof value === 'string' ? value : null;
}

function isGatheringStateActive(session: ContractSession | null): boolean {
  return ['active', 'probes_done', 'continuing'].includes(getGatheringState(session) || '');
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

function getStatusTone(status?: string | null): 'amber' | 'cyan' | 'emerald' | 'red' | 'zinc' {
  switch ((status || '').toLowerCase()) {
    case 'complete':
    case 'completed':
    case 'ready':
    case 'running':
    case 'success':
      return 'emerald';
    case 'failed':
    case 'error':
    case 'cancelled':
      return 'red';
    case 'waiting_for_input':
    case 'provisioning':
    case 'pending':
    case 'queued':
    case 'deciding':
    case 'cancelling':
      return 'amber';
    case 'stalled':
      return 'red';
    case 'idle':
    case 'not_provisioned':
      return 'zinc';
    default:
      return 'cyan';
  }
}

function getStatusIcon(status?: string | null): LucideIcon {
  switch (getStatusTone(status)) {
    case 'emerald':
      return CheckCircle2;
    case 'red':
      return XCircle;
    case 'amber':
      return Clock3;
    case 'cyan':
      return Activity;
    default:
      return CircleDot;
  }
}

function normalizeRuntimeStatus(status?: string | null): RuntimeProvisionStatus {
  switch ((status || '').toLowerCase()) {
    case 'failed':
    case 'error':
    case 'terminated':
      return 'failed';
    case 'not_provisioned':
    case 'idle':
    case '':
      return 'not_provisioned';
    case 'pending':
    case 'provisioning':
    case 'starting':
      return 'provisioning';
    default:
      return 'running';
  }
}

function getRuntimeStatusLabel(status: RuntimeProvisionStatus): string {
  return status.replace(/_/g, ' ');
}

function buildAiRepositoryPayload(
  repository: ContractRepository | null,
  branch: string
): { branch: string; name: string; owner: string } | null {
  if (!repository) {
    return null;
  }

  return {
    branch,
    name: repository.name,
    owner: getRepositoryOwner(repository),
  };
}

function withAuthorizationHeader(
  headers: HeadersInit | undefined,
  token: string | null | undefined
): Headers {
  const nextHeaders = new Headers(headers);

  if (token) {
    nextHeaders.set('Authorization', `Bearer ${token}`);
  }

  return nextHeaders;
}

function getNoticeIcon(tone: NoticeTone): LucideIcon {
  switch (tone) {
    case 'success':
      return CheckCircle2;
    case 'error':
      return AlertCircle;
    case 'info':
      return Activity;
  }
}

function getNoticeToneClass(tone: NoticeTone): string {
  switch (tone) {
    case 'success':
      return 'bg-emerald-500/12 text-emerald-200 shadow-[0_0_0_1px_rgba(16,185,129,0.28)]';
    case 'error':
      return 'bg-red-500/12 text-red-200 shadow-[0_0_0_1px_rgba(239,68,68,0.28)]';
    case 'info':
      return 'bg-cyan-500/12 text-cyan-100 shadow-[0_0_0_1px_rgba(34,211,238,0.24)]';
  }
}

function getMessageTokens(message: YudaiChatMessage): number {
  return message.metadata?.tokens || 0;
}

function getStatusDataText(data: YudaiStatusData): string {
  if (typeof data === 'string') {
    return data;
  }

  return data.message || data.status || '';
}

function getStatusDataTone(data: YudaiStatusData): NoticeTone {
  if (typeof data === 'string') {
    return 'info';
  }

  const rawTone = data.tone || data.level;
  return rawTone === 'success' || rawTone === 'error' ? rawTone : 'info';
}

function normalizeAgentQuestionInfo(data: YudaiAgentQuestionData): AgentQuestionInfo | null {
  if (!isRecord(data)) {
    return null;
  }

  const questionId = toOptionalString(data.question_id);
  const questionText = toOptionalString(data.question_text) || toOptionalString(data.prompt);

  if (!questionId || !questionText) {
    return null;
  }

  const rawOptions = Array.isArray(data.options) ? data.options : [];
  const options = rawOptions.flatMap((option) => {
    if (!isRecord(option)) {
      return [];
    }

    const id = toOptionalString(option.id);
    const label = toOptionalString(option.label);
    return id && label ? [{ id, label }] : [];
  });

  return {
    multi_select: Boolean(data.multi_select),
    options,
    question_id: questionId,
    question_text: questionText,
  };
}

function normalizeActionData(data: YudaiActionData): YudaiActionData | null {
  if (!isRecord(data)) {
    return null;
  }

  const actionType = toOptionalString(data.action_type);
  const label = toOptionalString(data.label);

  if (!actionType || !label) {
    return null;
  }

  return {
    action_type: actionType,
    issue_description: toOptionalString(data.issue_description) || null,
    issue_title: toOptionalString(data.issue_title) || null,
    label,
    labels: toStringArray(data.labels) || null,
  };
}

function formatJsonPreview(value: unknown): string {
  if (value === undefined) {
    return '';
  }

  if (typeof value === 'string') {
    return value;
  }

  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

export function AgentWorkbench(): JSX.Element {
  const { logout, sessionToken, user } = useAuth();
  const [activeView, setActiveView] = useState<WorkspaceView>('chat');
  const [branches, setBranches] = useState<ContractBranch[]>([]);
  const [contextCards, setContextCards] = useState<ContractContextCard[]>([]);
  const [currentSession, setCurrentSession] = useState<ContractSession | null>(null);
  const [draft, setDraft] = useState('');
  const [executionMode, setExecutionMode] = useState<ExecutionMode>('architect');
  const [executionObjective, setExecutionObjective] = useState('');
  const [executionStatus, setExecutionStatus] = useState<ContractExecutionStatus | null>(null);
  const [githubIssues, setGithubIssues] = useState<ContractGitHubIssue[]>([]);
  const [isBusy, setIsBusy] = useState(false);
  const [isLoadingBranches, setIsLoadingBranches] = useState(false);
  const [isLoadingRepos, setIsLoadingRepos] = useState(true);
  const [isRepositoryMenuOpen, setIsRepositoryMenuOpen] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [pendingQuestions, setPendingQuestions] = useState<ContractUserQuestion[]>([]);
  const [repositories, setRepositories] = useState<ContractRepository[]>([]);
  const [repoSearch, setRepoSearch] = useState('');
  const [runtime, setRuntime] = useState<ContractRuntime | null>(null);
  const [runtimeError, setRuntimeError] = useState<string | null>(null);
  const [runtimeStatus, setRuntimeStatus] = useState<RuntimeProvisionStatus>('not_provisioned');
  const [selectedBranch, setSelectedBranch] = useState('');
  const [selectedRepository, setSelectedRepository] = useState<ContractRepository | null>(null);
  const [sessionIssues, setSessionIssues] = useState<ContractIssue[]>([]);
  const [streamStatus, setStreamStatus] = useState<string | null>(null);
  const [trajectories, setTrajectories] = useState<ContractTrajectory[]>([]);
  const activeStreamSessionIdRef = useRef<string>('');
  const contextCardsRef = useRef<ContractContextCard[]>(contextCards);
  const currentSessionRef = useRef<ContractSession | null>(currentSession);
  const pendingDraftRef = useRef('');
  const selectedBranchRef = useRef(selectedBranch);
  const selectedRepositoryRef = useRef<ContractRepository | null>(selectedRepository);
  const sessionTokenRef = useRef<string | null | undefined>(sessionToken);

  const filteredRepositories = useMemo(() => {
    const query = repoSearch.trim().toLowerCase();

    if (!query) {
      return repositories;
    }

    return repositories.filter((repository) => (
      repository.full_name.toLowerCase().includes(query)
      || (repository.language || '').toLowerCase().includes(query)
      || (repository.description || '').toLowerCase().includes(query)
    ));
  }, [repositories, repoSearch]);

  const selectedOwner = selectedRepository ? getRepositoryOwner(selectedRepository) : '';
  const selectedRepoName = selectedRepository?.name || '';
  const selectedRepoLabel = selectedRepository?.full_name || 'No repository selected';
  const canCreateSession = Boolean(selectedRepository && selectedBranch && sessionToken && !isBusy);
  const hasSession = Boolean(currentSession);

  const pushNotice = useCallback(function showNotice(
    tone: NoticeTone,
    message: string
  ): void {
    setNotice({
      id: `${tone}_${Date.now()}`,
      message,
      tone,
    });
  }, []);

  const aiTransport = useMemo(() => new DefaultChatTransport<YudaiChatMessage>({
    api: buildApiUrl(API.AI.CHAT_STREAM, { sessionId: currentSessionRef.current?.session_id || 'pending' }),
    headers: (): Record<string, string> => (
      sessionTokenRef.current
        ? { Authorization: `Bearer ${sessionTokenRef.current}` }
        : {}
    ),
    prepareSendMessagesRequest: ({
      body,
      headers,
      messageId,
      messages: requestMessages,
      trigger,
    }) => {
      const sessionId = isRecord(body) && typeof body.session_id === 'string'
        ? body.session_id
        : currentSessionRef.current?.session_id || activeStreamSessionIdRef.current;

      if (!sessionId) {
        throw new Error('Missing active session for AI stream');
      }

      return {
        api: buildApiUrl(API.AI.CHAT_STREAM, { sessionId }),
        body: {
          context_card_ids: contextCardsRef.current.map((card) => String(card.id)),
          messageId: messageId ?? null,
          messages: requestMessages,
          repository: buildAiRepositoryPayload(
            selectedRepositoryRef.current,
            selectedBranchRef.current
          ),
          session_id: sessionId,
          trigger,
        },
        headers: withAuthorizationHeader(headers, sessionTokenRef.current),
      };
    },
  }), []);

  const {
    messages: chatMessages,
    sendMessage,
    setMessages: setChatMessages,
    status: chatStatus,
  } = useChat<YudaiChatMessage>({
    experimental_throttle: 40,
    onData(dataPart) {
      if (dataPart.type !== 'data-status') {
        return;
      }

      const message = getStatusDataText(dataPart.data);
      const tone = getStatusDataTone(dataPart.data);

      setStreamStatus(message || null);
      if (message && tone === 'error') {
        pushNotice('error', message);
      }
    },
    onError(error) {
      setDraft(pendingDraftRef.current);
      setStreamStatus(null);
      pushNotice('error', getErrorText(error, 'Message failed'));
    },
    onFinish({ isAbort, isError }) {
      const sessionId = activeStreamSessionIdRef.current;
      pendingDraftRef.current = '';
      setStreamStatus(null);

      if (!sessionId || isAbort || isError) {
        return;
      }

      void hydrateSession(sessionId).catch((error: unknown) => {
        pushNotice('error', getErrorText(error, 'Failed to refresh workspace'));
      });
    },
    transport: aiTransport,
  });

  const sessionStats = useMemo<SessionStats>(() => ({
    contextCount: contextCards.length,
    issueCount: sessionIssues.length || githubIssues.length,
    messageCount: currentSession?.total_messages || chatMessages.length,
    tokenCount: currentSession?.total_tokens || chatMessages.reduce((total, message) => (
      total + getMessageTokens(message)
    ), 0),
  }), [chatMessages, contextCards.length, currentSession, githubIssues.length, sessionIssues.length]);

  useEffect(() => {
    contextCardsRef.current = contextCards;
    currentSessionRef.current = currentSession;
    selectedBranchRef.current = selectedBranch;
    selectedRepositoryRef.current = selectedRepository;
    sessionTokenRef.current = sessionToken;
  }, [contextCards, currentSession, selectedBranch, selectedRepository, sessionToken]);

  useEffect(() => {
    let cancelled = false;

    async function loadRepositories(): Promise<void> {
      if (!sessionToken) {
        setIsLoadingRepos(false);
        return;
      }

      setIsLoadingRepos(true);

      try {
        const nextRepositories = await agentApi.listRepositories(sessionToken);

        if (cancelled) {
          return;
        }

        setRepositories(nextRepositories);
        setSelectedRepository((current) => current || nextRepositories[0] || null);
        setSelectedBranch((current) => current || (
          nextRepositories[0] ? getDefaultBranch(nextRepositories[0]) : ''
        ));
      } catch (error) {
        if (!cancelled) {
          pushNotice('error', getErrorText(error, 'Failed to load repositories'));
        }
      } finally {
        if (!cancelled) {
          setIsLoadingRepos(false);
        }
      }
    }

    void loadRepositories();

    return () => {
      cancelled = true;
    };
  }, [pushNotice, sessionToken]);

  useEffect(() => {
    let cancelled = false;

    async function loadRepositoryDetails(): Promise<void> {
      if (!selectedRepository || !sessionToken) {
        setBranches([]);
        setGithubIssues([]);
        return;
      }

      const owner = getRepositoryOwner(selectedRepository);
      setIsLoadingBranches(true);

      try {
        const [nextBranches, nextIssues] = await Promise.all([
          agentApi.listBranches(owner, selectedRepository.name, sessionToken),
          agentApi.listRepositoryIssues(owner, selectedRepository.name, sessionToken, 12),
        ]);

        if (cancelled) {
          return;
        }

        setBranches(nextBranches);
        setGithubIssues(nextIssues);
        setSelectedBranch((current) => (
          current || nextBranches[0]?.name || getDefaultBranch(selectedRepository)
        ));
      } catch (error) {
        if (!cancelled) {
          pushNotice('error', getErrorText(error, 'Failed to load repository details'));
        }
      } finally {
        if (!cancelled) {
          setIsLoadingBranches(false);
        }
      }
    }

    void loadRepositoryDetails();

    return () => {
      cancelled = true;
    };
  }, [pushNotice, selectedRepository, sessionToken]);

  useEffect(() => {
    if (!notice) {
      return undefined;
    }

    const timer = window.setTimeout(() => {
      setNotice(null);
    }, 4200);

    return () => window.clearTimeout(timer);
  }, [notice]);

  function handleRepositorySelect(repository: ContractRepository): void {
    activeStreamSessionIdRef.current = '';
    currentSessionRef.current = null;
    setSelectedRepository(repository);
    setSelectedBranch(getDefaultBranch(repository));
    setIsRepositoryMenuOpen(false);
    setCurrentSession(null);
    setContextCards([]);
    setExecutionObjective('');
    setExecutionStatus(null);
    setChatMessages([]);
    setPendingQuestions([]);
    setRepoSearch('');
    setRuntime(null);
    setRuntimeError(null);
    setRuntimeStatus('not_provisioned');
    setSessionIssues([]);
    setStreamStatus(null);
    setTrajectories([]);
  }

  async function hydrateSession(sessionId: string): Promise<ContractSessionContext | null> {
    if (!sessionToken) {
      return null;
    }

    const [
      context,
      cards,
      issues,
      execution,
      nextTrajectories,
    ] = await Promise.allSettled([
      agentApi.getSessionContext(sessionId, sessionToken),
      agentApi.listContextCards(sessionId, sessionToken),
      agentApi.listSessionIssues(sessionId, sessionToken, 20),
      agentApi.getExecutionStatus(sessionId, sessionToken),
      agentApi.listTrajectories(sessionId, sessionToken),
    ]);

    if (context.status === 'fulfilled') {
      activeStreamSessionIdRef.current = context.value.session.session_id;
      setCurrentSession(context.value.session);
      setChatMessages(context.value.messages.map(toAiMessage));
      setPendingQuestions(context.value.pending_questions || []);
    }

    if (cards.status === 'fulfilled') {
      setContextCards(cards.value);
    }

    if (issues.status === 'fulfilled') {
      setSessionIssues(issues.value);
    }

    if (execution.status === 'fulfilled') {
      setExecutionStatus(execution.value);
    }

    if (nextTrajectories.status === 'fulfilled') {
      setTrajectories(nextTrajectories.value);
    }

    return context.status === 'fulfilled' ? context.value : null;
  }

  async function refreshAfterDaifuActivity(sessionId: string): Promise<void> {
    const baseline = await hydrateSession(sessionId);
    if (!baseline) {
      return;
    }

    if ((baseline.pending_questions || []).length > 0) {
      return;
    }

    if (!isGatheringStateActive(baseline.session)) {
      return;
    }

    const baselineMessageCount = baseline.messages.length;
    for (let attempt = 0; attempt < 5; attempt += 1) {
      await delay(900);
      const nextContext = await hydrateSession(sessionId);
      if (!nextContext) {
        return;
      }

      if ((nextContext.pending_questions || []).length > 0) {
        return;
      }

      if (nextContext.messages.length > baselineMessageCount) {
        return;
      }

      if (!isGatheringStateActive(nextContext.session)) {
        return;
      }
    }
  }

  async function prepareRuntimeForSession(
    session: ContractSession,
    repository: ContractRepository,
    branch: string
  ): Promise<boolean> {
    if (!sessionToken) {
      return false;
    }

    setRuntime(null);
    setRuntimeError(null);
    setRuntimeStatus('provisioning');

    try {
      const nextRuntime = await agentApi.ensureRuntime(session.session_id, {
        environment: branch,
        org: 'yudai',
        repo_branch: branch,
        repo_name: repository.name,
        repo_owner: getRepositoryOwner(repository),
        repo_url: getRepositoryRuntimeUrl(repository),
      }, sessionToken);

      setRuntime(nextRuntime);
      setRuntimeStatus(normalizeRuntimeStatus(nextRuntime.status));
      setRuntimeError(null);
      return true;
    } catch (error) {
      const message = getErrorText(error, 'Runtime preparation failed');
      setRuntime(null);
      setRuntimeError(message);
      setRuntimeStatus('failed');
      return false;
    }
  }

  async function createSessionFromSelection({
    prepareRuntime = false,
  }: {
    prepareRuntime?: boolean;
  } = {}): Promise<ContractSession | null> {
    if (!selectedRepository || !selectedBranch || !sessionToken) {
      pushNotice('error', 'Select a repository before starting a session.');
      return null;
    }

    const repository = selectedRepository;
    const branch = selectedBranch;
    setIsBusy(true);

    try {
      const session = await agentApi.createSession({
        description: repository.description || null,
        repo_branch: branch,
        repo_name: repository.name,
        repo_owner: getRepositoryOwner(repository),
        title: `${repository.full_name}:${branch}`,
      }, sessionToken);

      setCurrentSession(session);
      activeStreamSessionIdRef.current = session.session_id;
      currentSessionRef.current = session;
      setChatMessages([]);
      setPendingQuestions([]);
      setContextCards([]);
      setSessionIssues([]);
      setTrajectories([]);
      setExecutionStatus(null);
      setRuntime(null);
      setRuntimeError(null);
      setRuntimeStatus('not_provisioned');

      if (prepareRuntime) {
        const isRuntimeReady = await prepareRuntimeForSession(session, repository, branch);
        pushNotice(
          isRuntimeReady ? 'success' : 'error',
          isRuntimeReady ? 'Session and runtime ready.' : 'Session ready, but runtime preparation failed.'
        );
      } else {
        pushNotice('success', 'Chat session ready.');
      }

      await refreshAfterDaifuActivity(session.session_id);
      return session;
    } catch (error) {
      pushNotice('error', getErrorText(error, 'Failed to start session'));
      return null;
    } finally {
      setIsBusy(false);
    }
  }

  async function ensureSession(): Promise<ContractSession | null> {
    if (currentSession) {
      return currentSession;
    }

    return createSessionFromSelection();
  }

  async function handleSessionSubmit(): Promise<void> {
    await createSessionFromSelection({ prepareRuntime: true });
  }

  async function handleRuntimeRetry(): Promise<void> {
    if (!currentSession || !selectedRepository || !selectedBranch) {
      pushNotice('error', 'Start a session before preparing runtime.');
      return;
    }

    setIsBusy(true);

    try {
      const isRuntimeReady = await prepareRuntimeForSession(
        currentSession,
        selectedRepository,
        selectedBranch
      );

      pushNotice(
        isRuntimeReady ? 'success' : 'error',
        isRuntimeReady ? 'Runtime ready.' : 'Runtime preparation failed.'
      );
    } finally {
      setIsBusy(false);
    }
  }

  async function handleRefresh(): Promise<void> {
    if (!currentSession) {
      return;
    }

    setIsBusy(true);

    try {
      await hydrateSession(currentSession.session_id);
      pushNotice('success', 'Workspace refreshed.');
    } catch (error) {
      pushNotice('error', getErrorText(error, 'Failed to refresh workspace'));
    } finally {
      setIsBusy(false);
    }
  }

  async function handleSendMessage(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();

    const content = draft.trim();
    if (!content || !sessionToken) {
      return;
    }

    const session = await ensureSession();
    if (!session) {
      return;
    }

    activeStreamSessionIdRef.current = session.session_id;
    pendingDraftRef.current = content;
    setStreamStatus(null);
    setDraft('');

    await sendMessage({
      metadata: { createdAt: new Date().toISOString() },
      text: content,
    }, {
      body: {
        session_id: session.session_id,
      },
    });
  }

  async function handleAnswerQuestion(
    questionId: string,
    selectedOptionIds: string[],
    answerText?: string
  ): Promise<void> {
    if (!currentSession || !sessionToken) {
      throw new Error('Missing active session');
    }

    await agentApi.answerQuestion(currentSession.session_id, questionId, {
      answer_text: answerText,
      resume_execution: true,
      selected_option_ids: selectedOptionIds,
    }, sessionToken);

    await refreshAfterDaifuActivity(currentSession.session_id);
  }

  async function handleStartExecution(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();

    const objective = capExecutionObjective(executionObjective);
    if (!objective || !sessionToken) {
      return;
    }

    const session = await ensureSession();
    if (!session) {
      return;
    }

    setIsBusy(true);

    try {
      const response = await agentApi.startExecution(session.session_id, {
        force_mode: executionMode,
        objective,
      }, sessionToken);

      setExecutionStatus(response);
      pushNotice('success', `${executionMode} run started.`);
    } catch (error) {
      pushNotice('error', getErrorText(error, 'Failed to start run'));
    } finally {
      setIsBusy(false);
    }
  }

  async function handleCancelExecution(): Promise<void> {
    if (!currentSession || !sessionToken) {
      return;
    }

    setIsBusy(true);

    try {
      await agentApi.cancelExecution(currentSession.session_id, sessionToken);
      await hydrateSession(currentSession.session_id);
      pushNotice('success', 'Run cancelled.');
    } catch (error) {
      pushNotice('error', getErrorText(error, 'Failed to cancel run'));
    } finally {
      setIsBusy(false);
    }
  }

  return (
    <div className="min-h-dvh bg-bg text-fg">
      <div className="fixed inset-0 -z-10 bg-[radial-gradient(circle_at_top_left,rgba(34,211,238,0.08),transparent_34%),linear-gradient(145deg,rgba(10,10,11,1),rgba(16,16,18,1)_48%,rgba(8,12,14,1))]" />

      <header className="sticky top-0 z-30 border-b border-border/80 bg-bg/88 backdrop-blur-xl">
        <div className="mx-auto flex min-h-16 w-full max-w-[1800px] items-center justify-between gap-3 px-4 sm:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <div className="grid size-10 shrink-0 place-items-center rounded-lg bg-amber/12 shadow-[0_0_0_1px_rgba(245,158,11,0.24)]">
              <Bot aria-hidden="true" className="size-5 text-amber" />
            </div>
            <div className="min-w-0">
              <h1 className="text-balance text-sm font-semibold tracking-normal text-fg sm:text-base">
                Yudai Agent Console
              </h1>
              <p className="truncate text-xs text-fg-muted">
                {selectedRepoLabel}
              </p>
            </div>
          </div>

          <div className="hidden min-w-0 items-center gap-2 md:flex">
            <StatusBadge label={currentSession?.mode_status || 'idle'} tone={getStatusTone(currentSession?.mode_status)} />
            <StatusBadge label={executionStatus?.status || 'no run'} tone={getStatusTone(executionStatus?.status)} />
            <StatusBadge label={getRuntimeStatusLabel(runtimeStatus)} tone={getStatusTone(runtimeStatus)} />
          </div>

          <div className="flex items-center gap-2">
            {notice && (
              <NoticePill notice={notice} />
            )}
            <button
              aria-label="Refresh workspace"
              className="grid size-11 place-items-center rounded-lg text-fg-secondary shadow-[0_0_0_1px_rgba(255,255,255,0.09)] transition-[background-color,box-shadow,color] duration-150 ease-out hover:bg-bg-tertiary hover:text-fg hover:shadow-[0_0_0_1px_rgba(255,255,255,0.15)] active:scale-[0.96]"
              disabled={!hasSession || isBusy}
              onClick={() => void handleRefresh()}
              type="button"
            >
              <RefreshCw aria-hidden="true" className={cx('size-4', isBusy && 'animate-spin')} />
            </button>
            <button
              aria-label="Sign out"
              className="grid size-11 place-items-center rounded-lg text-fg-secondary shadow-[0_0_0_1px_rgba(255,255,255,0.09)] transition-[background-color,box-shadow,color] duration-150 ease-out hover:bg-bg-tertiary hover:text-fg hover:shadow-[0_0_0_1px_rgba(255,255,255,0.15)] active:scale-[0.96]"
              onClick={() => void logout()}
              type="button"
            >
              <LogOut aria-hidden="true" className="size-4" />
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-[1800px] flex-col gap-4 px-4 py-4 sm:px-6">
        <RepositoryControlBar
          branches={branches}
          canCreateSession={canCreateSession}
          filteredRepositories={filteredRepositories}
          isBusy={isBusy}
          isLoadingBranches={isLoadingBranches}
          isLoadingRepos={isLoadingRepos}
          isRepositoryMenuOpen={isRepositoryMenuOpen}
          onBranchChange={setSelectedBranch}
          onCreateSession={() => void handleSessionSubmit()}
          onRepositoryMenuChange={setIsRepositoryMenuOpen}
          onRepositorySelect={handleRepositorySelect}
          onRetryRuntime={() => void handleRuntimeRetry()}
          onSearchChange={setRepoSearch}
          repositories={repositories}
          repoSearch={repoSearch}
          runtime={runtime}
          runtimeError={runtimeError}
          runtimeStatus={runtimeStatus}
          selectedBranch={selectedBranch}
          selectedRepository={selectedRepository}
        />

        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
          <section className="min-h-[calc(100dvh-10rem)] min-w-0 rounded-lg bg-bg-secondary/72 p-2 shadow-[0_0_0_1px_rgba(255,255,255,0.08)]">
            <div className="flex h-full min-h-[calc(100dvh-11rem)] flex-col rounded-md bg-bg-primary/70 shadow-[0_0_0_1px_rgba(255,255,255,0.06)]">
              <div className="flex flex-col gap-3 border-b border-border/75 p-3 sm:flex-row sm:items-center sm:justify-between">
                <WorkspaceTabs
                  activeView={activeView}
                  onViewChange={setActiveView}
                />
                <div className="grid grid-cols-4 gap-2 sm:flex">
                  <MetricTile icon={MessageSquareText} label="Msgs" value={formatCompactNumber(sessionStats.messageCount)} />
                  <MetricTile icon={Database} label="Tokens" value={formatCompactNumber(sessionStats.tokenCount)} />
                  <MetricTile icon={Layers3} label="Ctx" value={formatCompactNumber(sessionStats.contextCount)} />
                  <MetricTile icon={GitPullRequestArrow} label="Issues" value={formatCompactNumber(sessionStats.issueCount)} />
                </div>
              </div>

              {activeView === 'chat' && (
                <ChatPanel
                  chatStatus={chatStatus}
                  draft={draft}
                  isBusy={isBusy}
                  messages={chatMessages}
                  onAction={(action) => {
                    if (action.action_type.includes('execution') || action.action_type.includes('run')) {
                      setActiveView('execution');
                      return;
                    }

                    if (action.action_type.includes('context')) {
                      setActiveView('context');
                      return;
                    }

                    setActiveView('issues');
                  }}
                  onAnswerQuestion={(questionId, selectedOptionIds, answerText) => (
                    handleAnswerQuestion(questionId, selectedOptionIds, answerText)
                  )}
                  onDraftChange={setDraft}
                  onSubmit={(event) => void handleSendMessage(event)}
                  pendingQuestions={pendingQuestions}
                  selectedRepository={selectedRepository}
                  streamStatus={streamStatus}
                />
              )}

              {activeView === 'context' && (
                <ContextPanel
                  contextCards={contextCards}
                  currentSession={currentSession}
                />
              )}

              {activeView === 'execution' && (
                <ExecutionPanel
                  currentSession={currentSession}
                  executionMode={executionMode}
                  executionObjective={executionObjective}
                  executionStatus={executionStatus}
                  isBusy={isBusy}
                  onCancel={() => void handleCancelExecution()}
                  onModeChange={setExecutionMode}
                  onObjectiveChange={setExecutionObjective}
                  onSubmit={(event) => void handleStartExecution(event)}
                  trajectories={trajectories}
                />
              )}

              {activeView === 'issues' && (
                <IssuesPanel
                  githubIssues={githubIssues}
                  sessionIssues={sessionIssues}
                  selectedRepository={selectedRepository}
                />
              )}
            </div>
          </section>

          <aside className="grid auto-rows-max gap-4">
            <SessionPanel
              currentSession={currentSession}
              executionStatus={executionStatus}
              runtime={runtime}
              runtimeError={runtimeError}
              runtimeStatus={runtimeStatus}
              selectedBranch={selectedBranch}
              selectedOwner={selectedOwner}
              selectedRepoName={selectedRepoName}
              userName={user?.display_name || user?.github_username || 'Agent'}
            />
            <WorkflowPanel currentSession={currentSession} executionStatus={executionStatus} />
          </aside>
        </div>
      </main>
    </div>
  );
}

function NoticePill({ notice }: { notice: Notice }): JSX.Element {
  const Icon = getNoticeIcon(notice.tone);

  return (
    <div className={cx('hidden max-w-[280px] items-center gap-2 rounded-lg px-3 py-2 text-xs sm:flex', getNoticeToneClass(notice.tone))}>
      <Icon aria-hidden="true" className="size-4 shrink-0" />
      <span className="truncate">{notice.message}</span>
    </div>
  );
}

function StatusBadge({
  label,
  tone,
}: {
  label: string;
  tone: ReturnType<typeof getStatusTone>;
}): JSX.Element {
  const Icon = getStatusIcon(label);
  const toneClass = {
    amber: 'bg-amber/12 text-amber shadow-[0_0_0_1px_rgba(245,158,11,0.25)]',
    cyan: 'bg-cyan/12 text-cyan shadow-[0_0_0_1px_rgba(34,211,238,0.22)]',
    emerald: 'bg-emerald-500/12 text-emerald-200 shadow-[0_0_0_1px_rgba(16,185,129,0.25)]',
    red: 'bg-red-500/12 text-red-200 shadow-[0_0_0_1px_rgba(239,68,68,0.25)]',
    zinc: 'bg-white/5 text-fg-secondary shadow-[0_0_0_1px_rgba(255,255,255,0.09)]',
  }[tone];

  return (
    <span className={cx('inline-flex min-h-8 items-center gap-2 rounded-lg px-2.5 text-xs font-medium capitalize', toneClass)}>
      <Icon aria-hidden="true" className="size-3.5" />
      {label.replace(/_/g, ' ')}
    </span>
  );
}

function MetricTile({
  icon: Icon,
  label,
  value,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
}): JSX.Element {
  return (
    <div className="grid min-h-11 min-w-16 grid-cols-[auto_1fr] items-center gap-2 rounded-lg bg-white/[0.035] px-2.5 shadow-[0_0_0_1px_rgba(255,255,255,0.07)]">
      <Icon aria-hidden="true" className="size-3.5 text-cyan" />
      <div className="min-w-0">
        <div className="tabular-nums text-xs font-semibold text-fg">{value}</div>
        <div className="truncate text-[10px] uppercase tracking-normal text-fg-muted">{label}</div>
      </div>
    </div>
  );
}

function RepositoryControlBar({
  branches,
  canCreateSession,
  filteredRepositories,
  isBusy,
  isLoadingBranches,
  isLoadingRepos,
  isRepositoryMenuOpen,
  onBranchChange,
  onCreateSession,
  onRepositoryMenuChange,
  onRepositorySelect,
  onRetryRuntime,
  onSearchChange,
  repositories,
  repoSearch,
  runtime,
  runtimeError,
  runtimeStatus,
  selectedBranch,
  selectedRepository,
}: {
  branches: ContractBranch[];
  canCreateSession: boolean;
  filteredRepositories: ContractRepository[];
  isBusy: boolean;
  isLoadingBranches: boolean;
  isLoadingRepos: boolean;
  isRepositoryMenuOpen: boolean;
  onBranchChange: (branch: string) => void;
  onCreateSession: () => void;
  onRepositoryMenuChange: (open: boolean) => void;
  onRepositorySelect: (repository: ContractRepository) => void;
  onRetryRuntime: () => void;
  onSearchChange: (value: string) => void;
  repositories: ContractRepository[];
  repoSearch: string;
  runtime: ContractRuntime | null;
  runtimeError: string | null;
  runtimeStatus: RuntimeProvisionStatus;
  selectedBranch: string;
  selectedRepository: ContractRepository | null;
}): JSX.Element {
  const RuntimeIcon = getStatusIcon(runtimeStatus);
  const runtimeLabel = getRuntimeStatusLabel(runtimeStatus);

  return (
    <section className="rounded-lg bg-bg-secondary/72 p-3 shadow-[0_0_0_1px_rgba(255,255,255,0.08)]">
      <div className="grid gap-3 xl:grid-cols-[minmax(260px,1fr)_220px_auto_minmax(220px,0.7fr)] xl:items-end">
        <div className="relative min-w-0">
          <span className="mb-1.5 block text-xs font-medium text-fg-secondary">Repository</span>
          <button
            aria-controls="repository-switcher-menu"
            aria-expanded={isRepositoryMenuOpen}
            aria-label={`Selected repository ${selectedRepository?.full_name || 'none'}`}
            className="grid min-h-11 w-full grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 rounded-lg bg-bg-primary px-3 text-left shadow-[0_0_0_1px_rgba(255,255,255,0.09)] transition-[background-color,box-shadow,scale] duration-150 ease-out hover:bg-bg-tertiary hover:shadow-[0_0_0_1px_rgba(255,255,255,0.14)] active:scale-[0.96]"
            onClick={() => onRepositoryMenuChange(!isRepositoryMenuOpen)}
            type="button"
          >
            <FolderGit2 aria-hidden="true" className="size-4 text-cyan" />
            <span className="min-w-0">
              <span className="block truncate text-sm font-semibold text-fg">
                {selectedRepository?.full_name || 'Select repository'}
              </span>
              <span className="block truncate text-xs text-fg-muted">
                {formatCompactNumber(repositories.length)} repositories
              </span>
            </span>
            <ChevronDown aria-hidden="true" className={cx(
              'size-4 text-fg-muted transition-transform duration-150 ease-out',
              isRepositoryMenuOpen && 'rotate-180'
            )} />
          </button>

          {isRepositoryMenuOpen && (
            <div
              className="absolute left-0 top-[calc(100%+0.5rem)] z-40 w-full min-w-[320px] max-w-[calc(100vw-2rem)] rounded-lg bg-bg-secondary p-3 shadow-[0_24px_70px_rgba(0,0,0,0.48),0_0_0_1px_rgba(255,255,255,0.1)]"
              id="repository-switcher-menu"
            >
              <label className="relative block">
                <span className="sr-only">Search repositories</span>
                <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-fg-muted" />
                <input
                  className="min-h-11 w-full rounded-lg bg-bg-primary pl-10 pr-3 text-sm text-fg shadow-[0_0_0_1px_rgba(255,255,255,0.09)] outline-none transition-[box-shadow,background-color] duration-150 ease-out placeholder:text-fg-muted focus:shadow-[0_0_0_2px_rgba(34,211,238,0.45)]"
                  onChange={(event) => onSearchChange(event.target.value)}
                  placeholder="Search repositories"
                  value={repoSearch}
                />
              </label>

              <div className="mt-3 grid max-h-80 gap-2 overflow-y-auto pr-1">
                {isLoadingRepos && (
                  <LoadingRow label="Loading repositories" />
                )}

                {!isLoadingRepos && filteredRepositories.length === 0 && (
                  <EmptyState icon={FolderGit2} title="No repositories found" />
                )}

                {filteredRepositories.map((repository) => {
                  const isActive = selectedRepository?.id === repository.id;

                  return (
                    <button
                      className={cx(
                        'min-h-16 rounded-lg p-3 text-left shadow-[0_0_0_1px_rgba(255,255,255,0.08)] transition-[background-color,box-shadow,scale] duration-150 ease-out active:scale-[0.96]',
                        isActive
                          ? 'bg-cyan/10 shadow-[0_0_0_1px_rgba(34,211,238,0.28)]'
                          : 'bg-bg-primary/82 hover:bg-bg-tertiary hover:shadow-[0_0_0_1px_rgba(255,255,255,0.13)]'
                      )}
                      key={repository.id}
                      onClick={() => onRepositorySelect(repository)}
                      type="button"
                    >
                      <div className="flex items-start gap-2">
                        <FolderGit2 aria-hidden="true" className={cx('mt-0.5 size-4 shrink-0', isActive ? 'text-cyan' : 'text-fg-secondary')} />
                        <div className="min-w-0">
                          <div className="truncate text-sm font-medium text-fg">
                            {repository.full_name}
                          </div>
                          <div className="mt-1 flex flex-wrap gap-1.5 text-[11px] text-fg-muted">
                            <span>{repository.private ? 'Private' : 'Public'}</span>
                            {repository.language && <span>{repository.language}</span>}
                            <span>{formatCompactNumber(repository.open_issues_count)} issues</span>
                          </div>
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        <label className="block min-w-0">
          <span className="mb-1.5 block text-xs font-medium text-fg-secondary">Branch</span>
          <select
            className="min-h-11 w-full rounded-lg bg-bg-primary px-3 text-sm text-fg shadow-[0_0_0_1px_rgba(255,255,255,0.09)] outline-none transition-[box-shadow,background-color] duration-150 ease-out focus:shadow-[0_0_0_2px_rgba(34,211,238,0.45)]"
            disabled={!selectedRepository || isLoadingBranches}
            onChange={(event) => onBranchChange(event.target.value)}
            value={selectedBranch}
          >
            {selectedRepository && branches.length === 0 && (
              <option value={selectedBranch}>{selectedBranch || getDefaultBranch(selectedRepository)}</option>
            )}
            {branches.map((branch) => (
              <option key={branch.name} value={branch.name}>
                {branch.name}
              </option>
            ))}
          </select>
        </label>

        <button
          className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-amber px-4 pl-4 pr-3.5 text-sm font-semibold text-black transition-[background-color,scale] duration-150 ease-out hover:bg-yellow-400 active:scale-[0.96] disabled:cursor-not-allowed disabled:opacity-45 disabled:active:scale-100"
          disabled={!canCreateSession}
          onClick={onCreateSession}
          type="button"
        >
          {isBusy ? <Loader2 aria-hidden="true" className="size-4 animate-spin" /> : <Zap aria-hidden="true" className="size-4" />}
          Start session & prepare runtime
        </button>

        <div className="grid min-h-11 grid-cols-[auto_minmax(0,1fr)] items-center gap-3 rounded-lg bg-bg-primary px-3 shadow-[0_0_0_1px_rgba(255,255,255,0.08)]">
          <RuntimeIcon aria-hidden="true" className={cx(
            'size-4',
            runtimeStatus === 'failed' && 'text-red-200',
            runtimeStatus === 'not_provisioned' && 'text-fg-muted',
            runtimeStatus === 'provisioning' && 'text-amber',
            runtimeStatus === 'running' && 'text-emerald-200'
          )} />
          <div className="min-w-0">
            <div className="truncate text-xs font-semibold capitalize text-fg">
              Runtime {runtimeLabel}
            </div>
            <div className="truncate text-[11px] text-fg-muted">
              {runtime?.sandbox_id || runtime?.runtime_id || 'Controller sandbox'}
            </div>
          </div>
        </div>
      </div>

      <div className="mt-3 grid gap-2 text-xs text-fg-muted md:grid-cols-2">
        <div className="rounded-lg bg-bg-primary/68 px-3 py-2 shadow-[0_0_0_1px_rgba(255,255,255,0.06)]">
          Chat is answered by Daifu AI middleware through OpenRouter using OPENROUTER_MODEL, falling back to MSWEA_MODEL_NAME.
        </div>
        <div className="rounded-lg bg-bg-primary/68 px-3 py-2 shadow-[0_0_0_1px_rgba(255,255,255,0.06)]">
          Manual runs use Modal-backed mini-swe-agent execution; the backend planner decides safe next actions after each sandbox result.
        </div>
      </div>

      {runtimeStatus === 'failed' && runtimeError && (
        <div className="mt-3 flex flex-col gap-3 rounded-lg bg-red-500/10 px-3 py-3 text-sm text-red-100 shadow-[0_0_0_1px_rgba(239,68,68,0.26)] sm:flex-row sm:items-center sm:justify-between" role="alert">
          <span className="text-pretty">{runtimeError}</span>
          <button
            className="inline-flex min-h-10 shrink-0 items-center justify-center gap-2 rounded-lg bg-red-200 px-3 text-xs font-semibold text-red-950 transition-[background-color,scale] duration-150 ease-out hover:bg-red-100 active:scale-[0.96] disabled:cursor-not-allowed disabled:opacity-50"
            disabled={isBusy}
            onClick={onRetryRuntime}
            type="button"
          >
            {isBusy ? <Loader2 aria-hidden="true" className="size-3.5 animate-spin" /> : <RefreshCw aria-hidden="true" className="size-3.5" />}
            Retry runtime
          </button>
        </div>
      )}
    </section>
  );
}

function WorkspaceTabs({
  activeView,
  onViewChange,
}: {
  activeView: WorkspaceView;
  onViewChange: (view: WorkspaceView) => void;
}): JSX.Element {
  return (
    <div className="grid grid-cols-4 gap-1 rounded-lg bg-bg-secondary p-1 shadow-[0_0_0_1px_rgba(255,255,255,0.08)]">
      {WORKSPACE_TABS.map((tab) => {
        const Icon = tab.icon;
        const isActive = activeView === tab.id;

        return (
          <button
            className={cx(
              'inline-flex min-h-10 items-center justify-center gap-2 rounded-md px-3 text-sm font-medium transition-[background-color,color,scale] duration-150 ease-out active:scale-[0.96]',
              isActive
                ? 'bg-cyan/12 text-cyan shadow-[0_0_0_1px_rgba(34,211,238,0.16)]'
                : 'text-fg-secondary hover:bg-white/5 hover:text-fg'
            )}
            key={tab.id}
            onClick={() => onViewChange(tab.id)}
            type="button"
          >
            <Icon aria-hidden="true" className="size-4" />
            <span className="hidden sm:inline">{tab.label}</span>
          </button>
        );
      })}
    </div>
  );
}

function ChatPanel({
  chatStatus,
  draft,
  isBusy,
  messages,
  onAction,
  onAnswerQuestion,
  onDraftChange,
  onSubmit,
  pendingQuestions,
  selectedRepository,
  streamStatus,
}: {
  chatStatus: 'submitted' | 'streaming' | 'ready' | 'error';
  draft: string;
  isBusy: boolean;
  messages: YudaiChatMessage[];
  onAction: (action: YudaiActionData) => void;
  onAnswerQuestion: (
    questionId: string,
    selectedOptionIds: string[],
    answerText?: string
  ) => Promise<void>;
  onDraftChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  pendingQuestions: ContractUserQuestion[];
  selectedRepository: ContractRepository | null;
  streamStatus: string | null;
}): JSX.Element {
  const isChatBusy = chatStatus === 'submitted' || chatStatus === 'streaming';

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto p-3 sm:p-4">
        {messages.length === 0 ? (
          <EmptyState
            icon={MessageSquareText}
            title={selectedRepository ? 'Chat is ready' : 'No repository selected'}
          />
        ) : (
          <div className="grid gap-3">
            {messages.map((message) => (
              <MessageBubble
                key={message.id}
                message={message}
                onAction={onAction}
                onAnswerQuestion={onAnswerQuestion}
              />
            ))}
            {streamStatus && (
              <div className="inline-flex w-fit items-center gap-2 rounded-lg bg-cyan/10 px-3 py-2 text-xs text-cyan shadow-[0_0_0_1px_rgba(34,211,238,0.18)]">
                <Loader2 aria-hidden="true" className="size-3 animate-spin" />
                {streamStatus}
              </div>
            )}
          </div>
        )}
      </div>

      {pendingQuestions.length > 0 && (
        <div className="grid gap-3 border-t border-border/75 bg-bg-secondary/30 px-3 py-3">
          {pendingQuestions.map((question) => (
            <UserQuestionPrompt
              key={question.question_id}
              question={toAgentQuestionInfo(question)}
              onSubmit={(selectedOptionIds, answerText) => (
                onAnswerQuestion(question.question_id, selectedOptionIds, answerText)
              )}
            />
          ))}
        </div>
      )}

      <form className="border-t border-border/75 p-3" onSubmit={onSubmit}>
        <label className="block">
          <span className="sr-only">Message</span>
          <textarea
            className="min-h-28 w-full resize-none rounded-lg bg-bg-secondary p-3 text-sm leading-6 text-fg shadow-[0_0_0_1px_rgba(255,255,255,0.08)] outline-none transition-[box-shadow,background-color] duration-150 ease-out placeholder:text-fg-muted focus:shadow-[0_0_0_2px_rgba(34,211,238,0.45)]"
            onChange={(event) => onDraftChange(event.target.value)}
            placeholder="Ask the agent"
            value={draft}
          />
        </label>
        <div className="mt-3 flex items-center justify-between gap-3">
          <p className="text-xs text-fg-muted">
            {selectedRepository?.full_name || 'No repository selected'}
          </p>
          <button
            className="inline-flex min-h-11 items-center gap-2 rounded-lg bg-cyan px-4 pl-4 pr-3.5 text-sm font-semibold text-black transition-[background-color,scale] duration-150 ease-out hover:bg-sky-300 active:scale-[0.96] disabled:cursor-not-allowed disabled:opacity-45 disabled:active:scale-100"
            disabled={isBusy || isChatBusy || !draft.trim()}
            type="submit"
          >
            {isBusy || isChatBusy ? <Loader2 aria-hidden="true" className="size-4 animate-spin" /> : <Send aria-hidden="true" className="size-4" />}
            Send
          </button>
        </div>
      </form>
    </div>
  );
}

function MessageBubble({
  message,
  onAction,
  onAnswerQuestion,
}: {
  message: YudaiChatMessage;
  onAction: (action: YudaiActionData) => void;
  onAnswerQuestion: (
    questionId: string,
    selectedOptionIds: string[],
    answerText?: string
  ) => Promise<void>;
}): JSX.Element {
  const isUser = message.role === 'user';
  const Icon = isUser ? Github : Bot;

  return (
    <article className={cx('flex gap-3', isUser && 'flex-row-reverse')}>
      <div className={cx(
        'grid size-9 shrink-0 place-items-center rounded-lg shadow-[0_0_0_1px_rgba(255,255,255,0.08)]',
        isUser ? 'bg-amber/12 text-amber' : 'bg-cyan/12 text-cyan'
      )}>
        <Icon aria-hidden="true" className="size-4" />
      </div>
      <div className={cx(
        'max-w-[min(720px,100%)] rounded-lg px-4 py-3 shadow-[0_0_0_1px_rgba(255,255,255,0.08)]',
        isUser ? 'bg-amber/10' : 'bg-bg-secondary',
        message.metadata?.error && 'bg-red-500/10 shadow-[0_0_0_1px_rgba(239,68,68,0.26)]'
      )}>
        <div className="mb-1 flex items-center gap-2 text-[11px] font-medium uppercase tracking-normal text-fg-muted">
          <span>{message.role}</span>
          <span className="tabular-nums">
            {message.metadata?.createdAt ? formatDateTime(message.metadata.createdAt) : 'Now'}
          </span>
          {!isUser && message.metadata?.modelUsed && (
            <span className="truncate normal-case text-cyan">
              {message.metadata.modelUsed}
            </span>
          )}
        </div>
        <div className="grid gap-2">
          {message.parts.map((part, index) => (
            <MessagePart
              key={`${message.id}_${index}_${part.type}`}
              messageId={message.id}
              onAction={onAction}
              onAnswerQuestion={onAnswerQuestion}
              part={part}
            />
          ))}
        </div>
      </div>
    </article>
  );
}

function MessagePart({
  messageId,
  onAction,
  onAnswerQuestion,
  part,
}: {
  messageId: string;
  onAction: (action: YudaiActionData) => void;
  onAnswerQuestion: (
    questionId: string,
    selectedOptionIds: string[],
    answerText?: string
  ) => Promise<void>;
  part: YudaiMessagePart;
}): JSX.Element | null {
  if (part.type === 'text') {
    return (
      <p className="whitespace-pre-wrap text-pretty text-sm leading-6 text-fg-secondary">
        {part.text}
      </p>
    );
  }

  if (part.type === 'data-status') {
    const message = getStatusDataText(part.data);

    if (!message) {
      return null;
    }

    return (
      <div className={cx('inline-flex w-fit items-center gap-2 rounded-lg px-3 py-2 text-xs', getNoticeToneClass(getStatusDataTone(part.data)))}>
        <Activity aria-hidden="true" className="size-3.5" />
        {message}
      </div>
    );
  }

  if (part.type === 'data-agent-question') {
    const question = normalizeAgentQuestionInfo(part.data);

    if (!question) {
      return null;
    }

    return (
      <UserQuestionPrompt
        question={question}
        onSubmit={(selectedOptionIds, answerText) => (
          onAnswerQuestion(question.question_id, selectedOptionIds, answerText)
        )}
      />
    );
  }

  if (part.type === 'data-action') {
    const action = normalizeActionData(part.data);

    if (!action) {
      return null;
    }

    return (
      <button
        className="inline-flex min-h-9 w-fit items-center gap-2 rounded-lg bg-amber/14 px-3 text-xs font-semibold text-amber shadow-[0_0_0_1px_rgba(245,158,11,0.24)] transition-[background-color,scale] duration-150 ease-out hover:bg-amber/20 active:scale-[0.96]"
        onClick={() => onAction(action)}
        type="button"
      >
        <ArrowRight aria-hidden="true" className="size-3.5" />
        {action.label}
      </button>
    );
  }

  if (isToolUIPart(part)) {
    return <ToolActivityRow part={part} />;
  }

  if (part.type === 'reasoning' && part.text) {
    return (
      <details className="rounded-lg bg-bg-primary/70 px-3 py-2 text-xs text-fg-muted shadow-[0_0_0_1px_rgba(255,255,255,0.07)]">
        <summary className="cursor-pointer text-fg-secondary">Reasoning</summary>
        <p className="mt-2 whitespace-pre-wrap leading-5">{part.text}</p>
      </details>
    );
  }

  if (part.type === 'source-url') {
    return (
      <a
        className="inline-flex min-h-9 w-fit items-center gap-2 rounded-lg bg-bg-primary px-3 text-xs text-fg-secondary shadow-[0_0_0_1px_rgba(255,255,255,0.08)] transition-colors hover:text-fg"
        href={part.url}
        rel="noreferrer"
        target="_blank"
      >
        <ExternalLink aria-hidden="true" className="size-3.5" />
        {part.title || part.url}
      </a>
    );
  }

  if (part.type === 'source-document') {
    return (
      <div className="rounded-lg bg-bg-primary/70 px-3 py-2 text-xs text-fg-secondary shadow-[0_0_0_1px_rgba(255,255,255,0.07)]">
        {part.title || part.filename || part.mediaType}
      </div>
    );
  }

  if (part.type === 'file') {
    return (
      <a
        className="inline-flex min-h-9 w-fit items-center gap-2 rounded-lg bg-bg-primary px-3 text-xs text-fg-secondary shadow-[0_0_0_1px_rgba(255,255,255,0.08)] transition-colors hover:text-fg"
        href={part.url}
        rel="noreferrer"
        target="_blank"
      >
        <ExternalLink aria-hidden="true" className="size-3.5" />
        {part.filename || part.mediaType}
      </a>
    );
  }

  if (part.type === 'step-start') {
    return (
      <div className="text-[11px] uppercase tracking-normal text-fg-muted">
        Step started
      </div>
    );
  }

  return (
    <span className="sr-only">
      Unrendered part for {messageId}
    </span>
  );
}

function ToolActivityRow({
  part,
}: {
  part: Extract<YudaiMessagePart, { type: `tool-${string}` | 'dynamic-tool' }>;
}): JSX.Element {
  const toolName = getToolName(part);
  const preview = part.state === 'output-available'
    ? formatJsonPreview(part.output)
    : part.state === 'output-error'
      ? part.errorText
      : formatJsonPreview(part.input);

  return (
    <div className="rounded-lg bg-bg-primary/70 px-3 py-2 text-xs shadow-[0_0_0_1px_rgba(255,255,255,0.07)]">
      <div className="flex items-center justify-between gap-3 text-fg-secondary">
        <span className="inline-flex min-w-0 items-center gap-2">
          <TerminalSquare aria-hidden="true" className="size-3.5 shrink-0 text-cyan" />
          <span className="truncate">{toolName}</span>
        </span>
        <span className="shrink-0 capitalize text-fg-muted">{part.state.replace(/-/g, ' ')}</span>
      </div>
      {preview && (
        <pre className="mt-2 max-h-28 overflow-auto whitespace-pre-wrap text-[11px] leading-5 text-fg-muted">
          {preview}
        </pre>
      )}
    </div>
  );
}

function ContextPanel({
  contextCards,
  currentSession,
}: {
  contextCards: ContractContextCard[];
  currentSession: ContractSession | null;
}): JSX.Element {
  if (!currentSession) {
    return (
      <EmptyState icon={Layers3} title="No active session" />
    );
  }

  if (contextCards.length === 0) {
    return (
      <EmptyState icon={Layers3} title="No context cards" />
    );
  }

  return (
    <div className="grid content-start gap-3 overflow-y-auto p-3 sm:grid-cols-2 sm:p-4 xl:grid-cols-3">
      {contextCards.map((card) => (
        <article
          className="rounded-lg bg-bg-secondary p-4 shadow-[0_0_0_1px_rgba(255,255,255,0.08)] transition-[box-shadow,background-color] duration-150 ease-out hover:bg-bg-tertiary hover:shadow-[0_0_0_1px_rgba(255,255,255,0.14)]"
          key={card.id}
        >
          <div className="mb-3 flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h3 className="text-balance text-sm font-semibold">{card.title}</h3>
              <p className="mt-1 line-clamp-2 text-pretty text-xs text-fg-muted">{card.description}</p>
            </div>
            <StatusBadge label={card.source} tone="zinc" />
          </div>
          <p className="line-clamp-5 text-pretty text-sm leading-6 text-fg-secondary">
            {card.content}
          </p>
          <div className="mt-4 flex items-center justify-between text-xs text-fg-muted">
            <span className="tabular-nums">{formatCompactNumber(card.tokens)} tokens</span>
            <span>{formatDateTime(card.created_at)}</span>
          </div>
        </article>
      ))}
    </div>
  );
}

function ExecutionPanel({
  currentSession,
  executionMode,
  executionObjective,
  executionStatus,
  isBusy,
  onCancel,
  onModeChange,
  onObjectiveChange,
  onSubmit,
  trajectories,
}: {
  currentSession: ContractSession | null;
  executionMode: ExecutionMode;
  executionObjective: string;
  executionStatus: ContractExecutionStatus | null;
  isBusy: boolean;
  onCancel: () => void;
  onModeChange: (mode: ExecutionMode) => void;
  onObjectiveChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  trajectories: ContractTrajectory[];
}): JSX.Element {
  return (
    <div className="grid min-h-0 flex-1 gap-4 overflow-y-auto p-3 sm:p-4 xl:grid-cols-[minmax(0,1fr)_360px]">
      <form className="rounded-lg bg-bg-secondary p-4 shadow-[0_0_0_1px_rgba(255,255,255,0.08)]" onSubmit={onSubmit}>
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h2 className="text-balance text-base font-semibold">Lifecycle run</h2>
            <p className="text-xs text-fg-muted">{currentSession?.session_id || 'No active session'}</p>
          </div>
          {executionStatus && (
            <StatusBadge label={executionStatus.status} tone={getStatusTone(executionStatus.status)} />
          )}
        </div>

        <div className="mb-4 grid grid-cols-3 gap-2">
          {EXECUTION_MODES.map((mode) => {
            const Icon = mode.icon;
            const isActive = executionMode === mode.id;

            return (
              <button
                className={cx(
                  'inline-flex min-h-11 items-center justify-center gap-2 rounded-lg px-3 text-sm font-medium transition-[background-color,color,scale] duration-150 ease-out active:scale-[0.96]',
                  isActive
                    ? 'bg-amber/14 text-amber shadow-[0_0_0_1px_rgba(245,158,11,0.25)]'
                    : 'bg-bg-primary text-fg-secondary shadow-[0_0_0_1px_rgba(255,255,255,0.08)] hover:bg-bg-tertiary hover:text-fg'
                )}
                key={mode.id}
                onClick={() => onModeChange(mode.id)}
                type="button"
              >
                <Icon aria-hidden="true" className="size-4" />
                <span className="hidden sm:inline">{mode.label}</span>
                <span className="sr-only">{mode.role}</span>
              </button>
            );
          })}
        </div>

        <label className="block">
          <span className="mb-1.5 block text-xs font-medium text-fg-secondary">Objective</span>
          <textarea
            className="min-h-44 w-full resize-none rounded-lg bg-bg-primary p-3 text-sm leading-6 text-fg shadow-[0_0_0_1px_rgba(255,255,255,0.08)] outline-none transition-[box-shadow,background-color] duration-150 ease-out placeholder:text-fg-muted focus:shadow-[0_0_0_2px_rgba(245,158,11,0.38)]"
            onChange={(event) => onObjectiveChange(event.target.value)}
            placeholder="Fix the selected issue and open a PR"
            value={executionObjective}
          />
        </label>

        <div className="mt-4 flex flex-wrap gap-2">
          <button
            className="inline-flex min-h-11 items-center gap-2 rounded-lg bg-amber px-4 pl-4 pr-3.5 text-sm font-semibold text-black transition-[background-color,scale] duration-150 ease-out hover:bg-yellow-400 active:scale-[0.96] disabled:cursor-not-allowed disabled:opacity-45 disabled:active:scale-100"
            disabled={isBusy || !executionObjective.trim()}
            type="submit"
          >
            {isBusy ? <Loader2 aria-hidden="true" className="size-4 animate-spin" /> : <Play aria-hidden="true" className="size-4" />}
            Start run
          </button>
          <button
            className="inline-flex min-h-11 items-center gap-2 rounded-lg bg-bg-primary px-4 text-sm font-medium text-fg-secondary shadow-[0_0_0_1px_rgba(255,255,255,0.09)] transition-[background-color,color,scale] duration-150 ease-out hover:bg-bg-tertiary hover:text-fg active:scale-[0.96] disabled:cursor-not-allowed disabled:opacity-45 disabled:active:scale-100"
            disabled={!executionStatus || isBusy}
            onClick={onCancel}
            type="button"
          >
            <Square aria-hidden="true" className="size-4" />
            Cancel
          </button>
        </div>
      </form>

      <div className="grid content-start gap-3">
        {trajectories.length === 0 ? (
          <EmptyState icon={Activity} title="No trajectories" />
        ) : (
          trajectories.map((trajectory) => (
            <article
              className="rounded-lg bg-bg-secondary p-4 shadow-[0_0_0_1px_rgba(255,255,255,0.08)]"
              key={trajectory.id}
            >
              <div className="mb-2 flex items-center justify-between gap-3">
                <h3 className="truncate text-sm font-semibold">{trajectory.run_id}</h3>
                <StatusBadge label={trajectory.status} tone={getStatusTone(trajectory.status)} />
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs text-fg-muted">
                <span>{trajectory.model_name || trajectory.model}</span>
                <span className="text-right tabular-nums">{formatCompactNumber(trajectory.total_messages)} msgs</span>
                <span>{formatDateTime(trajectory.created_at)}</span>
                <span className="text-right tabular-nums">${formatCompactNumber(trajectory.instance_cost)}</span>
              </div>
            </article>
          ))
        )}
      </div>
    </div>
  );
}

function IssuesPanel({
  githubIssues,
  selectedRepository,
  sessionIssues,
}: {
  githubIssues: ContractGitHubIssue[];
  selectedRepository: ContractRepository | null;
  sessionIssues: ContractIssue[];
}): JSX.Element {
  const sourceLabel = sessionIssues.length > 0 ? 'Session issues' : 'GitHub issues';

  if (!selectedRepository) {
    return (
      <EmptyState icon={GitPullRequestArrow} title="No repository selected" />
    );
  }

  const items = sessionIssues.length > 0
    ? sessionIssues.map((issue) => ({
      href: issue.github_issue_url || undefined,
      id: issue.issue_id,
      meta: `${issue.priority} / ${issue.status}`,
      title: issue.title,
    }))
    : githubIssues.map((issue) => ({
      href: issue.html_url || undefined,
      id: String(issue.number),
      meta: `#${issue.number} / ${issue.state}`,
      title: issue.title,
    }));

  if (items.length === 0) {
    return (
      <EmptyState icon={GitPullRequestArrow} title="No issues found" />
    );
  }

  return (
    <div className="min-h-0 overflow-y-auto p-3 sm:p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-balance text-base font-semibold">{sourceLabel}</h2>
        <StatusBadge label={selectedRepository.full_name} tone="zinc" />
      </div>
      <div className="grid gap-3">
        {items.map((issue) => (
          <article
            className="rounded-lg bg-bg-secondary p-4 shadow-[0_0_0_1px_rgba(255,255,255,0.08)] transition-[box-shadow,background-color] duration-150 ease-out hover:bg-bg-tertiary hover:shadow-[0_0_0_1px_rgba(255,255,255,0.14)]"
            key={issue.id}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="mb-1 text-xs text-fg-muted">{issue.meta}</p>
                <h3 className="text-balance text-sm font-semibold">{issue.title}</h3>
              </div>
              {issue.href && (
                <a
                  aria-label={`Open ${issue.title}`}
                  className="grid size-10 shrink-0 place-items-center rounded-lg text-fg-secondary shadow-[0_0_0_1px_rgba(255,255,255,0.09)] transition-[background-color,color,scale] duration-150 ease-out hover:bg-bg-primary hover:text-fg active:scale-[0.96]"
                  href={issue.href}
                  rel="noreferrer"
                  target="_blank"
                >
                  <ExternalLink aria-hidden="true" className="size-4" />
                </a>
              )}
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

function SessionPanel({
  currentSession,
  executionStatus,
  runtime,
  runtimeError,
  runtimeStatus,
  selectedBranch,
  selectedOwner,
  selectedRepoName,
  userName,
}: {
  currentSession: ContractSession | null;
  executionStatus: ContractExecutionStatus | null;
  runtime: ContractRuntime | null;
  runtimeError: string | null;
  runtimeStatus: RuntimeProvisionStatus;
  selectedBranch: string;
  selectedOwner: string;
  selectedRepoName: string;
  userName: string;
}): JSX.Element {
  return (
    <section className="rounded-lg bg-bg-secondary/72 p-4 shadow-[0_0_0_1px_rgba(255,255,255,0.08)]">
      <div className="mb-4 flex items-center gap-3">
        <div className="grid size-10 place-items-center rounded-lg bg-cyan/12 text-cyan shadow-[0_0_0_1px_rgba(34,211,238,0.2)]">
          <Bot aria-hidden="true" className="size-5" />
        </div>
        <div className="min-w-0">
          <h2 className="truncate text-sm font-semibold">{userName}</h2>
          <p className="text-xs text-fg-muted">{currentSession?.session_id || 'No active session'}</p>
        </div>
      </div>

      <div className="grid gap-2 text-sm">
        <InfoRow icon={FolderGit2} label="Owner" value={selectedOwner || 'Unselected'} />
        <InfoRow icon={Github} label="Repo" value={selectedRepoName || 'Unselected'} />
        <InfoRow icon={GitBranch} label="Branch" value={selectedBranch || 'Unselected'} />
        <InfoRow icon={Activity} label="Mode" value={currentSession?.current_mode || 'pending'} />
        <InfoRow icon={TerminalSquare} label="Run" value={executionStatus?.status || 'idle'} />
        <InfoRow icon={Zap} label="Runtime" value={getRuntimeStatusLabel(runtimeStatus)} />
      </div>

      {runtime?.sandbox_id && (
        <p className="mt-3 truncate rounded-lg bg-bg-primary px-3 py-2 text-xs text-fg-muted shadow-[0_0_0_1px_rgba(255,255,255,0.07)]">
          Sandbox {runtime.sandbox_id}
        </p>
      )}

      {runtimeError && (
        <p className="mt-3 text-pretty rounded-lg bg-red-500/10 px-3 py-2 text-xs text-red-100 shadow-[0_0_0_1px_rgba(239,68,68,0.22)]">
          {runtimeError}
        </p>
      )}

      {currentSession?.repo_url && (
        <a
          className="mt-4 inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg bg-bg-primary px-4 text-sm font-medium text-fg-secondary shadow-[0_0_0_1px_rgba(255,255,255,0.09)] transition-[background-color,color,scale] duration-150 ease-out hover:bg-bg-tertiary hover:text-fg active:scale-[0.96]"
          href={currentSession.repo_url}
          rel="noreferrer"
          target="_blank"
        >
          Open repository
          <ExternalLink aria-hidden="true" className="size-4" />
        </a>
      )}
    </section>
  );
}

function WorkflowPanel({
  currentSession,
  executionStatus,
}: {
  currentSession: ContractSession | null;
  executionStatus: ContractExecutionStatus | null;
}): JSX.Element {
  const currentMode = currentSession?.current_mode || executionStatus?.mode || 'pending';

  return (
    <section className="rounded-lg bg-bg-secondary/72 p-4 shadow-[0_0_0_1px_rgba(255,255,255,0.08)]">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <h2 className="text-balance text-sm font-semibold">Adversarial Lifecycle</h2>
          <p className="text-xs text-fg-muted">Backend-enforced legal progression</p>
        </div>
        <Sparkles aria-hidden="true" className="size-5 text-amber" />
      </div>

      <div className="grid gap-3">
        {EXECUTION_MODES.map((mode, index) => {
          const isActive = currentMode === mode.id;
          const Icon = mode.icon;

          return (
            <div className="grid grid-cols-[auto_1fr] items-center gap-3" key={mode.id}>
              <div className={cx(
                'grid size-9 place-items-center rounded-lg shadow-[0_0_0_1px_rgba(255,255,255,0.08)]',
                isActive ? 'bg-amber/14 text-amber' : 'bg-bg-primary text-fg-muted'
              )}>
                <Icon aria-hidden="true" className="size-4" />
              </div>
              <div className="min-w-0">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-medium">{mode.label}</p>
                  <span className="tabular-nums text-xs text-fg-muted">0{index + 1}</span>
                </div>
                <p className="mt-0.5 truncate text-xs text-fg-muted">{mode.role}</p>
                <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-bg-primary">
                  <div className={cx(
                    'h-full rounded-full transition-[width,background-color] duration-200 ease-out',
                    isActive ? 'w-3/4 bg-amber' : 'w-1/4 bg-white/12'
                  )} />
                </div>
                <p className="mt-1 text-pretty text-[11px] leading-4 text-fg-muted">{mode.description}</p>
              </div>
            </div>
          );
        })}
      </div>

      <p className="mt-4 rounded-lg bg-bg-primary/70 px-3 py-2 text-xs leading-5 text-fg-muted shadow-[0_0_0_1px_rgba(255,255,255,0.06)]">
        Architect -&gt; Tester -&gt; Coder is controlled by the backend; manual run requests are rejected unless the requested mode is the next legal mode.
      </p>
    </section>
  );
}

function InfoRow({
  icon: Icon,
  label,
  value,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
}): JSX.Element {
  return (
    <div className="grid min-h-10 grid-cols-[auto_74px_1fr] items-center gap-2 rounded-lg bg-bg-primary px-3 shadow-[0_0_0_1px_rgba(255,255,255,0.07)]">
      <Icon aria-hidden="true" className="size-4 text-fg-muted" />
      <span className="text-xs text-fg-muted">{label}</span>
      <span className="truncate text-right text-xs font-medium text-fg-secondary">{value}</span>
    </div>
  );
}

function EmptyState({
  icon: Icon,
  title,
}: {
  icon: LucideIcon;
  title: string;
}): JSX.Element {
  return (
    <div className="grid min-h-44 place-items-center rounded-lg bg-bg-secondary/70 p-6 text-center shadow-[0_0_0_1px_rgba(255,255,255,0.06)]">
      <div>
        <div className="mx-auto mb-3 grid size-11 place-items-center rounded-lg bg-white/[0.04] text-fg-muted shadow-[0_0_0_1px_rgba(255,255,255,0.08)]">
          <Icon aria-hidden="true" className="size-5" />
        </div>
        <p className="text-balance text-sm font-medium text-fg-secondary">{title}</p>
      </div>
    </div>
  );
}

function LoadingRow({ label }: { label: string }): JSX.Element {
  return (
    <div className="flex min-h-16 items-center gap-3 rounded-lg bg-bg-primary px-3 text-sm text-fg-secondary shadow-[0_0_0_1px_rgba(255,255,255,0.08)]">
      <Loader2 aria-hidden="true" className="size-4 animate-spin text-cyan" />
      {label}
    </div>
  );
}
