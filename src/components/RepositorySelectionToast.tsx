import React, { useState, useEffect, useCallback } from 'react';
import { ChevronDown, Github, GitBranch, Check, X, Loader2 } from 'lucide-react';
import { GitHubRepository, GitHubBranch, SelectedRepository } from '../types';
import { useSessionStore } from '../stores/sessionStore';

interface RepositorySelectionToastProps {
  isOpen: boolean;
  onConfirm: (selection: SelectedRepository) => void;
  onCancel: () => void;
}

export const RepositorySelectionToast: React.FC<RepositorySelectionToastProps> = ({
  isOpen,
  onConfirm,
  onCancel
}) => {
  const [branches, setBranches] = useState<GitHubBranch[]>([]);
  const [selectedRepository, setSelectedRepository] = useState<GitHubRepository | null>(null);
  const [selectedBranch, setSelectedBranch] = useState<string>('');
  const [loadingBranches, setLoadingBranches] = useState(false);
  const [isRepoDropdownOpen, setIsRepoDropdownOpen] = useState(false);
  const [isBranchDropdownOpen, setIsBranchDropdownOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { loadRepositoryBranches } = useSessionStore();

  // Use session store for repository state
  const {
    availableRepositories,
    isLoadingRepositories,
    repositoryError,
    setRepositoryLoading
  } = useSessionStore();

  const loadRepositories = useCallback(async () => {
    console.log('Loading repositories...');
    setRepositoryLoading(true);
    setError(null);

    try {
      // Use unified sessionStore method to load repositories
      // The loadRepositories method in sessionStore will handle the API call
      // and update the availableRepositories state automatically
      const { loadRepositories: loadReposFromStore } = useSessionStore.getState();
      await loadReposFromStore();

      console.log('Repositories loaded successfully via sessionStore');
    } catch (error) {
      console.error('Failed to load repositories:', error);
      setError('Failed to load repositories. Please try again.');
    } finally {
      setRepositoryLoading(false);
    }
  }, [setRepositoryLoading]);

  const loadBranches = useCallback(async () => {
    if (!selectedRepository) return;

    console.log('Loading branches for repository:', selectedRepository.full_name);
    setLoadingBranches(true);
    setSelectedBranch('');
    setBranches([]);

    try {
      const [owner, repo] = selectedRepository.full_name.split('/');
      console.log('Fetching branches for:', { owner, repo });
      const branchList = await loadRepositoryBranches(owner, repo);
      console.log('Received branch list:', branchList);

      // Transform API response to match frontend GitHubBranch type
      const transformedBranches: GitHubBranch[] = branchList.map(branch => ({
        name: branch.name,
        commit: branch.commit,
        protected: false // API doesn't provide this, set default
      }));

      console.log('Transformed branches:', transformedBranches);
      setBranches(transformedBranches);

      // Auto-select main or master branch if available, or default branch
      const defaultBranch = transformedBranches.find(b =>
        b.name === 'main' || b.name === 'master' || b.name === selectedRepository.default_branch
      );
      if (defaultBranch) {
        console.log('Auto-selecting default branch:', defaultBranch.name);
        setSelectedBranch(defaultBranch.name);
      } else if (transformedBranches.length > 0) {
        console.log('Auto-selecting first branch:', transformedBranches[0].name);
        setSelectedBranch(transformedBranches[0].name);
      }
    } catch (error) {
      console.error('Failed to load branches:', error);
      setError('Failed to load branches. Please try again.');
    } finally {
      setLoadingBranches(false);
    }
  }, [selectedRepository, loadRepositoryBranches]);

  // Load repositories when toast opens
  useEffect(() => {
    if (isOpen && availableRepositories.length === 0) {
      console.log('Loading repositories...');
      loadRepositories();
    }
  }, [isOpen, availableRepositories.length, loadRepositories]);

  // Load branches when repository is selected
  useEffect(() => {
    if (selectedRepository) {
      console.log('Repository selected, loading branches...');
      loadBranches();
    }
  }, [selectedRepository, loadBranches]);

  // Set error from repository context
  useEffect(() => {
    if (repositoryError) {
      console.log('Repository error:', repositoryError);
      setError(repositoryError);
    }
  }, [repositoryError]);

  const handleConfirm = () => {
    if (selectedRepository && selectedBranch) {
      console.log('Confirming selection:', {
        repository: selectedRepository.full_name,
        branch: selectedBranch
      });
      onConfirm({
        repository: selectedRepository,
        branch: selectedBranch
      });
    }
  };

  const handleRepositorySelect = (repo: GitHubRepository) => {
    console.log('Repository selected:', repo.full_name);
    setSelectedRepository(repo);
    setIsRepoDropdownOpen(false);
  };

  const handleBranchSelect = (branchName: string) => {
    console.log('Branch selected:', branchName);
    setSelectedBranch(branchName);
    setIsBranchDropdownOpen(false);
  };

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40" />

      {/* Toast */}
      <div className="fixed top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 z-50">
        <div className="bg-bg-secondary border border-border rounded-xl shadow-terminal p-6 w-[500px] max-w-[90vw] animate-fade-in">
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-amber/10 border border-amber/20 flex items-center justify-center glow-amber">
                <Github className="w-5 h-5 text-amber" />
              </div>
              <div>
                <h2 className="text-lg font-mono font-semibold text-fg">Select Repository</h2>
                <p className="text-xs font-mono text-muted">Choose a repository and branch to analyze</p>
              </div>
            </div>
            <button
              onClick={onCancel}
              className="p-2 hover:bg-bg-tertiary rounded-lg transition-colors text-muted hover:text-fg"
              aria-label="Cancel"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Error Message */}
          {error && (
            <div className="mb-4 p-3 bg-error/10 border border-error/30 rounded-lg animate-fade-in">
              <p className="text-sm text-error font-mono">{error}</p>
            </div>
          )}

          {/* Repository Selection */}
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-mono font-medium text-muted uppercase tracking-wider mb-2">
                Repository
              </label>
              <div className="relative">
                <button
                  onClick={() => setIsRepoDropdownOpen(!isRepoDropdownOpen)}
                  disabled={isLoadingRepositories}
                  className="w-full flex items-center justify-between px-4 py-3 bg-bg-tertiary border border-border rounded-lg text-fg hover:border-border-accent transition-all duration-200 disabled:opacity-50"
                >
                  <span className="flex items-center gap-2 font-mono text-sm">
                    {isLoadingRepositories ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin text-amber" />
                        <span className="text-muted">Loading repositories...</span>
                      </>
                    ) : selectedRepository ? (
                      <>
                        <Github className="w-4 h-4 text-muted" />
                        <span>{selectedRepository.full_name}</span>
                      </>
                    ) : (
                      <span className="text-muted">Select a repository</span>
                    )}
                  </span>
                  <ChevronDown className={`w-4 h-4 transition-transform duration-200 ${isRepoDropdownOpen ? 'rotate-180' : ''}`} />
                </button>

                {isRepoDropdownOpen && availableRepositories.length > 0 && (
                  <div className="absolute top-full left-0 right-0 mt-2 bg-bg-secondary border border-border rounded-xl shadow-terminal max-h-64 overflow-y-auto z-10 animate-fade-in">
                    {availableRepositories.map((repo) => (
                      <button
                        key={repo.id}
                        onClick={() => handleRepositorySelect(repo)}
                        className="w-full px-4 py-3 text-left hover:bg-bg-tertiary transition-colors border-b border-border/50 last:border-b-0"
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="text-fg font-mono text-sm font-medium">{repo.full_name}</p>
                            {repo.description && (
                              <p className="text-muted text-xs font-mono truncate mt-0.5">{repo.description}</p>
                            )}
                          </div>
                          <div className="flex items-center gap-2 text-xs font-mono">
                            {repo.language && (
                              <span className="px-2 py-1 bg-bg-tertiary border border-border rounded-lg text-muted">{repo.language}</span>
                            )}
                            {repo.private && (
                              <span className="px-2 py-1 bg-amber/10 border border-amber/20 text-amber rounded-lg">Private</span>
                            )}
                          </div>
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Branch Selection */}
            <div>
              <label className="block text-xs font-mono font-medium text-muted uppercase tracking-wider mb-2">
                Branch
              </label>
              <div className="relative">
                <button
                  onClick={() => setIsBranchDropdownOpen(!isBranchDropdownOpen)}
                  disabled={!selectedRepository || loadingBranches}
                  className="w-full flex items-center justify-between px-4 py-3 bg-bg-tertiary border border-border rounded-lg text-fg hover:border-border-accent transition-all duration-200 disabled:opacity-50"
                >
                  <span className="flex items-center gap-2 font-mono text-sm">
                    {loadingBranches ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin text-cyan" />
                        <span className="text-muted">Loading branches...</span>
                      </>
                    ) : selectedBranch ? (
                      <>
                        <GitBranch className="w-4 h-4 text-muted" />
                        <span>{selectedBranch}</span>
                      </>
                    ) : (
                      <span className="text-muted">Select a branch</span>
                    )}
                  </span>
                  <ChevronDown className={`w-4 h-4 transition-transform duration-200 ${isBranchDropdownOpen ? 'rotate-180' : ''}`} />
                </button>

                {isBranchDropdownOpen && branches.length > 0 && (
                  <div className="absolute top-full left-0 right-0 mt-2 bg-bg-secondary border border-border rounded-xl shadow-terminal max-h-48 overflow-y-auto z-10 animate-fade-in">
                    {branches.map((branch) => (
                      <button
                        key={branch.name}
                        onClick={() => handleBranchSelect(branch.name)}
                        className="w-full px-4 py-3 text-left hover:bg-bg-tertiary transition-colors border-b border-border/50 last:border-b-0"
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-fg font-mono text-sm">{branch.name}</span>
                          {branch.protected && (
                            <span className="text-xs font-mono text-amber">Protected</span>
                          )}
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-3 mt-6 pt-4 border-t border-border">
            <button
              onClick={onCancel}
              className="flex-1 px-4 py-2.5 text-fg hover:bg-bg-tertiary rounded-lg transition-colors font-mono text-sm border border-border"
            >
              Cancel
            </button>
            <button
              onClick={handleConfirm}
              disabled={!selectedRepository || !selectedBranch}
              className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-amber hover:bg-amber/90 disabled:bg-bg-tertiary disabled:border-border disabled:text-muted text-bg-primary rounded-lg font-mono text-sm font-semibold transition-all duration-200 disabled:cursor-not-allowed border border-amber disabled:border-border glow-amber disabled:shadow-none"
            >
              <Check className="w-4 h-4" />
              Confirm Selection
            </button>
          </div>
        </div>
      </div>
    </>
  );
};
