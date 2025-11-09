import React, { useState, useCallback } from 'react';
import { X, ExternalLink, GitBranch, FileText, MessageSquare, Tag, Clock, Check } from 'lucide-react';
import type { GitHubIssuePreview, ChatContextMessage, FileContextItem } from '../types/api';
import { UserIssueResponse } from '../types';
import { useSessionStore } from '../stores/sessionStore';

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
      
      // Check for success or if github_url exists (issue was created even if response parsing failed)
      if (response?.success || response?.github_url) {
        setGithubIssueCreated(true);
        setGithubIssueUrl(response.github_url);
      } else {
        showError(response?.message || 'Failed to create GitHub issue');
      }
      
    } catch (error) {
      console.error('Failed to create GitHub issue:', error);
      
      // Check if error response contains github_url (issue was created despite error)
      const errorResponse = error as { response?: { data?: { github_url?: string } }; github_url?: string };
      const githubUrl = errorResponse?.response?.data?.github_url || errorResponse?.github_url;
      if (githubUrl) {
        console.log('GitHub issue created successfully despite error:', githubUrl);
        setGithubIssueCreated(true);
        setGithubIssueUrl(githubUrl);
      } else {
        const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
        showError(`Failed to create GitHub issue: ${errorMessage}`);
      }
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
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-bg border border-zinc-800 rounded-2xl shadow-2xl w-full max-w-6xl h-[85vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-zinc-800">
          <div className="flex items-center gap-4">
            <FileText className="w-5 h-5 text-primary" />
            <div>
              <h2 className="text-lg font-semibold text-fg">GitHub Issue Preview</h2>
              <p className="text-sm text-fg/60">
                {issuePreview.repositoryInfo 
                  ? `${issuePreview.repositoryInfo.owner}/${issuePreview.repositoryInfo.name}` 
                  : 'No repository selected'}
              </p>
            </div>
            {githubIssueCreated && (
              <span className="bg-success/20 text-success px-3 py-1 rounded-full text-xs font-medium flex items-center gap-1">
                <Check className="w-3 h-3" />
                Created
              </span>
            )}
          </div>

          <button
            onClick={onClose}
            className="p-2 hover:bg-zinc-800 rounded-lg transition-colors"
            aria-label="Close modal"
          >
            <X className="w-5 h-5 text-fg" />
          </button>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mx-6 mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
            <p className="text-sm text-red-400">{error}</p>
            <button
              onClick={() => setError(null)}
              className="mt-2 text-xs text-red-300 hover:text-red-200 underline"
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
                <h3 className="text-xl font-semibold text-fg mb-2">{issuePreview.title}</h3>
                <div className="flex items-center gap-2 mb-4">
                  {issuePreview.labels.map((label, index) => (
                    <span
                      key={index}
                      className="bg-primary/20 text-primary px-2 py-1 rounded text-xs font-medium flex items-center gap-1"
                    >
                      <Tag className="w-3 h-3" />
                      {label}
                    </span>
                  ))}
                </div>
              </div>

              {/* Issue Body */}
              <div className="border border-zinc-800 rounded-lg">
                <div className="bg-zinc-900/50 px-4 py-2 border-b border-zinc-800">
                  <span className="text-sm font-medium text-fg">Issue Description</span>
                </div>
                <div className="p-4">
                  <pre className="text-sm text-fg whitespace-pre-wrap font-sans">
                    {issuePreview.body}
                  </pre>
                </div>
              </div>

              {/* Repository Information */}
              {issuePreview.repositoryInfo && (
                <div className="border border-zinc-800 rounded-lg">
                  <div className="bg-zinc-900/50 px-4 py-2 border-b border-zinc-800">
                    <span className="text-sm font-medium text-fg flex items-center gap-2">
                      <GitBranch className="w-4 h-4" />
                      Repository Information
                    </span>
                  </div>
                  <div className="p-4">
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div>
                        <span className="text-fg/60">Owner:</span>
                        <span className="text-fg ml-2">{issuePreview.repositoryInfo.owner}</span>
                      </div>
                      <div>
                        <span className="text-fg/60">Repository:</span>
                        <span className="text-fg ml-2">{issuePreview.repositoryInfo.name}</span>
                      </div>
                      {issuePreview.repositoryInfo.branch && (
                        <div>
                          <span className="text-fg/60">Branch:</span>
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
              <div className="border border-zinc-800 rounded-lg">
                <div className="bg-zinc-900/50 px-4 py-2 border-b border-zinc-800">
                  <span className="text-sm font-medium text-fg flex items-center gap-2">
                    <Clock className="w-4 h-4" />
                    Metadata
                  </span>
                </div>
                <div className="p-4 space-y-3">
                  <div className="flex justify-between text-sm">
                    <span className="text-fg/60">Chat Messages:</span>
                    <span className="text-fg">{issuePreview.metadata.chat_messages_count}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-fg/60">File Context:</span>
                    <span className="text-fg">{issuePreview.metadata.file_context_count}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-fg/60">Total Tokens:</span>
                    <span className="text-fg">{issuePreview.metadata.total_tokens.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-fg/60">Generated:</span>
                    <span className="text-fg">{new Date(issuePreview.metadata.generated_at).toLocaleTimeString()}</span>
                  </div>
                </div>
              </div>

              {/* Chat Context */}
              {issuePreview.conversationContext.length > 0 && (
                <div className="border border-zinc-800 rounded-lg">
                  <div className="bg-zinc-900/50 px-4 py-2 border-b border-zinc-800">
                    <span className="text-sm font-medium text-fg flex items-center gap-2">
                      <MessageSquare className="w-4 h-4" />
                      Chat Context ({issuePreview.conversationContext.length})
                    </span>
                  </div>
                  <div className="p-4 max-h-48 overflow-y-auto space-y-2">
                    {issuePreview.conversationContext.slice(-5).map((msg, index) => (
                      <div key={index} className="text-xs">
                        <div className={`p-2 rounded ${msg.isCode ? 'bg-zinc-900' : 'bg-zinc-800/50'}`}>
                          <div className="text-fg/60 mb-1">
                            {msg.isCode ? 'Code' : 'Message'}
                          </div>
                          <div className="text-fg">
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
                <div className="border border-zinc-800 rounded-lg">
                  <div className="bg-zinc-900/50 px-4 py-2 border-b border-zinc-800">
                    <span className="text-sm font-medium text-fg flex items-center gap-2">
                      <FileText className="w-4 h-4" />
                      File Context ({issuePreview.fileContext.length})
                    </span>
                  </div>
                  <div className="p-4 max-h-48 overflow-y-auto space-y-1">
                    {issuePreview.fileContext.slice(0, 10).map((file, index) => (
                      <div key={index} className="flex justify-between items-center text-xs">
                        <span className="text-fg truncate">{file.name}</span>
                        <span className="text-fg/60 ml-2">{file.tokens} tokens</span>
                      </div>
                    ))}
                    {issuePreview.fileContext.length > 10 && (
                      <div className="text-xs text-fg/60 pt-2">
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
        <div className="p-6 border-t border-zinc-800 flex justify-between items-center">
          <div className="text-sm text-fg/60">
            {githubIssueCreated ? (
              <span className="text-green-400">✓ GitHub issue created successfully</span>
            ) : issuePreview?.canCreateGitHubIssue ? (
              'Ready to create GitHub issue'
            ) : (
              'Repository access required to create GitHub issue'
            )}
          </div>
          <div className="flex gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 text-fg hover:bg-zinc-800 rounded-lg transition-colors"
            >
              Close
            </button>
            {githubIssueCreated ? (
              <button
                onClick={handleOpenGitHubIssue}
                className="flex items-center gap-2 bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg transition-colors"
              >
                Open GitHub Issue
                <ExternalLink className="w-4 h-4" />
              </button>
            ) : (
              <button
                onClick={handleCreateGitHubIssue}
                disabled={!issuePreview?.canCreateGitHubIssue || isCreatingGitHubIssue || !issuePreview?.userIssue}
                className="flex items-center gap-2 bg-primary hover:bg-primary/80 disabled:opacity-50
                         disabled:cursor-not-allowed text-white px-4 py-2 rounded-lg transition-colors"
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
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
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

