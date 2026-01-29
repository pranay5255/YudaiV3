import React, { useState, useCallback } from 'react';
import { X, ExternalLink, GitBranch, FileText, MessageSquare, Tag, Clock, Check } from 'lucide-react';
import type { GitHubIssuePreview, ChatContextMessage, FileContextItem } from '../types/api';
import { UserIssueResponse } from '../types';
import { useSessionStore } from '../stores/sessionStore';
import { logger } from '../utils/logger';

interface IssuePreviewData extends GitHubIssuePreview {
  userIssue?: UserIssueResponse;
  conversationContext: ChatContextMessage[];
  fileContext: FileContextItem[];
  canCreateGitHubIssue: boolean;
  repositoryInfo?: {
    owner: string;
    name: string;
    branch?: string;
  };
}

interface DiffModalProps {
  isOpen: boolean;
  onClose: () => void;
  issuePreview?: IssuePreviewData;
  onShowError?: (error: string) => void;
}

export const DiffModal: React.FC<DiffModalProps> = ({
  isOpen,
  onClose,
  issuePreview,
  onShowError
}) => {
  const [isCreatingGitHubIssue, setIsCreatingGitHubIssue] = useState(false);
  const [githubIssueCreated, setGithubIssueCreated] = useState(false);
  const [githubIssueUrl, setGithubIssueUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { createGitHubIssueFromUserIssue } = useSessionStore();

  const showError = useCallback((message: string) => {
    setError(message);
    if (onShowError) {
      onShowError(message);
    }
  }, [onShowError]);

  const handleCreateGitHubIssue = useCallback(async () => {
    if (!issuePreview?.canCreateGitHubIssue || !issuePreview?.userIssue) {
      showError('Cannot create GitHub issue: missing issue data or repository access');
      return;
    }

    setIsCreatingGitHubIssue(true);
    setError(null);

    try {
      const response = await createGitHubIssueFromUserIssue(issuePreview.userIssue.issue_id);

      if (response?.success && response?.github_url) {
        setGithubIssueCreated(true);
        setGithubIssueUrl(response.github_url);
      } else {
        showError(response?.message || 'Failed to create GitHub issue');
      }

    } catch (error) {
      logger.error('[DiffModal] Failed to create GitHub issue:', error);
      const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
      showError(`Failed to create GitHub issue: ${errorMessage}`);
    } finally {
      setIsCreatingGitHubIssue(false);
    }
  }, [issuePreview, createGitHubIssueFromUserIssue, showError]);

  const handleOpenGitHubIssue = useCallback(() => {
    if (githubIssueUrl) {
      window.open(githubIssueUrl, '_blank', 'noopener,noreferrer');
    }
  }, [githubIssueUrl]);

  if (!isOpen || !issuePreview) return null;

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-bg-secondary border border-border rounded-xl shadow-terminal w-full max-w-6xl h-[85vh] flex flex-col animate-fade-in">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-border">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-lg bg-amber/10 border border-amber/20 flex items-center justify-center">
              <FileText className="w-5 h-5 text-amber" />
            </div>
            <div>
              <h2 className="text-lg font-mono font-semibold text-fg">GitHub Issue Preview</h2>
              <p className="text-xs font-mono text-muted">
                {issuePreview.repositoryInfo
                  ? `${issuePreview.repositoryInfo.owner}/${issuePreview.repositoryInfo.name}`
                  : 'No repository selected'}
              </p>
            </div>
            {githubIssueCreated && (
              <span className="bg-success/10 text-success border border-success/20 px-3 py-1.5 rounded-lg text-xs font-mono font-medium flex items-center gap-1.5">
                <Check className="w-3 h-3" />
                Created
              </span>
            )}
          </div>

          <button
            onClick={onClose}
            className="p-2 hover:bg-bg-tertiary rounded-lg transition-colors text-muted hover:text-fg"
            aria-label="Close modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mx-6 mt-4 p-3 bg-error/10 border border-error/30 rounded-lg animate-fade-in">
            <p className="text-sm text-error font-mono">{error}</p>
            <button
              onClick={() => setError(null)}
              className="mt-2 text-xs text-error/80 hover:text-error underline font-mono"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Content */}
        <div className="flex-1 overflow-auto">
          <div className="grid grid-cols-3 gap-6 p-6 h-full">
            {/* Left Column - Issue Content */}
            <div className="col-span-2 space-y-6">
              {/* Issue Title */}
              <div>
                <h3 className="text-xl font-mono font-semibold text-fg mb-3">{issuePreview.title}</h3>
                <div className="flex items-center gap-2 mb-4 flex-wrap">
                  {issuePreview.labels.map((label, index) => (
                    <span
                      key={index}
                      className="bg-cyan/10 text-cyan border border-cyan/20 px-2.5 py-1 rounded-lg text-xs font-mono flex items-center gap-1.5"
                    >
                      <Tag className="w-3 h-3" />
                      {label}
                    </span>
                  ))}
                </div>
              </div>

              {/* Issue Body */}
              <div className="border border-border rounded-xl overflow-hidden">
                <div className="bg-bg-tertiary px-4 py-2.5 border-b border-border flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber" />
                  <span className="text-xs font-mono font-medium text-fg-secondary uppercase tracking-wider">Issue Description</span>
                </div>
                <div className="p-4 bg-bg-tertiary/50">
                  <pre className="text-sm text-fg-secondary whitespace-pre-wrap font-mono leading-relaxed">
                    {issuePreview.body}
                  </pre>
                </div>
              </div>

              {/* Repository Information */}
              {issuePreview.repositoryInfo && (
                <div className="border border-border rounded-xl overflow-hidden">
                  <div className="bg-bg-tertiary px-4 py-2.5 border-b border-border flex items-center gap-2">
                    <GitBranch className="w-4 h-4 text-cyan" />
                    <span className="text-xs font-mono font-medium text-fg-secondary uppercase tracking-wider">Repository Information</span>
                  </div>
                  <div className="p-4 bg-bg-tertiary/50">
                    <div className="grid grid-cols-2 gap-4 text-sm font-mono">
                      <div>
                        <span className="text-muted">Owner:</span>
                        <span className="text-fg ml-2">{issuePreview.repositoryInfo.owner}</span>
                      </div>
                      <div>
                        <span className="text-muted">Repository:</span>
                        <span className="text-fg ml-2">{issuePreview.repositoryInfo.name}</span>
                      </div>
                      {issuePreview.repositoryInfo.branch && (
                        <div>
                          <span className="text-muted">Branch:</span>
                          <span className="text-fg ml-2">{issuePreview.repositoryInfo.branch}</span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Right Column - Context & Metadata */}
            <div className="space-y-4">
              {/* Metadata */}
              <div className="border border-border rounded-xl overflow-hidden">
                <div className="bg-bg-tertiary px-4 py-2.5 border-b border-border flex items-center gap-2">
                  <Clock className="w-4 h-4 text-amber" />
                  <span className="text-xs font-mono font-medium text-fg-secondary uppercase tracking-wider">Metadata</span>
                </div>
                <div className="p-4 bg-bg-tertiary/50 space-y-2.5">
                  <div className="flex justify-between text-xs font-mono">
                    <span className="text-muted">Chat Messages:</span>
                    <span className="text-fg">{issuePreview.metadata.chat_messages_count}</span>
                  </div>
                  <div className="flex justify-between text-xs font-mono">
                    <span className="text-muted">File Context:</span>
                    <span className="text-fg">{issuePreview.metadata.file_context_count}</span>
                  </div>
                  <div className="flex justify-between text-xs font-mono">
                    <span className="text-muted">Total Tokens:</span>
                    <span className="text-fg">{issuePreview.metadata.total_tokens.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between text-xs font-mono">
                    <span className="text-muted">Generated:</span>
                    <span className="text-fg">{new Date(issuePreview.metadata.generated_at).toLocaleTimeString()}</span>
                  </div>
                </div>
              </div>

              {/* Chat Context */}
              {issuePreview.conversationContext.length > 0 && (
                <div className="border border-border rounded-xl overflow-hidden">
                  <div className="bg-bg-tertiary px-4 py-2.5 border-b border-border flex items-center gap-2">
                    <MessageSquare className="w-4 h-4 text-cyan" />
                    <span className="text-xs font-mono font-medium text-fg-secondary uppercase tracking-wider">
                      Chat Context ({issuePreview.conversationContext.length})
                    </span>
                  </div>
                  <div className="p-3 bg-bg-tertiary/50 max-h-48 overflow-y-auto space-y-2">
                    {issuePreview.conversationContext.slice(-5).map((msg, index) => (
                      <div key={index} className="text-xs">
                        <div className={`p-2.5 rounded-lg ${msg.isCode ? 'bg-bg-secondary border border-border' : 'bg-bg-secondary/50'}`}>
                          <div className="text-muted mb-1 font-mono text-[10px] uppercase tracking-wider">
                            {msg.isCode ? 'Code' : 'Message'}
                          </div>
                          <div className="text-fg-secondary font-mono leading-relaxed">
                            {msg.content.length > 100 ? `${msg.content.substring(0, 100)}...` : msg.content}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* File Context */}
              {issuePreview.fileContext.length > 0 && (
                <div className="border border-border rounded-xl overflow-hidden">
                  <div className="bg-bg-tertiary px-4 py-2.5 border-b border-border flex items-center gap-2">
                    <FileText className="w-4 h-4 text-success" />
                    <span className="text-xs font-mono font-medium text-fg-secondary uppercase tracking-wider">
                      File Context ({issuePreview.fileContext.length})
                    </span>
                  </div>
                  <div className="p-3 bg-bg-tertiary/50 max-h-48 overflow-y-auto space-y-1">
                    {issuePreview.fileContext.slice(0, 10).map((file, index) => (
                      <div key={index} className="flex justify-between items-center text-xs font-mono py-1">
                        <span className="text-fg-secondary truncate">{file.name}</span>
                        <span className="text-muted ml-2">{file.tokens} tokens</span>
                      </div>
                    ))}
                    {issuePreview.fileContext.length > 10 && (
                      <div className="text-xs text-muted pt-2 font-mono">
                        +{issuePreview.fileContext.length - 10} more files...
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-border flex justify-between items-center">
          <div className="text-sm text-muted font-mono">
            {githubIssueCreated ? (
              <span className="text-success flex items-center gap-2">
                <Check className="w-4 h-4" />
                GitHub issue created successfully
              </span>
            ) : issuePreview?.canCreateGitHubIssue ? (
              <span className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
                Ready to create GitHub issue
              </span>
            ) : (
              <span className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-amber" />
                Repository access required
              </span>
            )}
          </div>
          <div className="flex gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2.5 text-fg hover:bg-bg-tertiary rounded-lg transition-colors font-mono text-sm border border-border"
            >
              Close
            </button>
            {githubIssueCreated ? (
              <button
                onClick={handleOpenGitHubIssue}
                className="flex items-center gap-2 bg-success hover:bg-success/90 text-bg-primary px-5 py-2.5 rounded-lg font-mono text-sm font-semibold transition-all duration-200 glow-emerald"
              >
                Open GitHub Issue
                <ExternalLink className="w-4 h-4" />
              </button>
            ) : (
              <button
                onClick={handleCreateGitHubIssue}
                disabled={!issuePreview?.canCreateGitHubIssue || isCreatingGitHubIssue || !issuePreview?.userIssue}
                className="flex items-center gap-2 bg-amber hover:bg-amber/90 disabled:bg-bg-tertiary disabled:border-border disabled:text-muted text-bg-primary px-5 py-2.5 rounded-lg font-mono text-sm font-semibold transition-all duration-200 disabled:cursor-not-allowed border border-amber disabled:border-border glow-amber disabled:shadow-none"
                title={
                  !issuePreview?.canCreateGitHubIssue
                    ? 'Repository access required'
                    : !issuePreview?.userIssue
                      ? 'Issue data not available'
                      : 'Create GitHub issue'
                }
              >
                {isCreatingGitHubIssue ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-2 border-bg-primary/20 border-t-bg-primary" />
                    Creating...
                  </>
                ) : (
                  <>
                    Create GitHub Issue
                    <ExternalLink className="w-4 h-4" />
                  </>
                )}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
