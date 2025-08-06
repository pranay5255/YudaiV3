import React, { useState, useEffect, useCallback } from 'react';
import { ChevronDown, Github, GitBranch, Check, X, Loader2 } from 'lucide-react';
import { GitHubRepository, GitHubBranch, SelectedRepository } from '../types';
import { ApiService } from '../services/api';
import { useAuth } from '../hooks/useAuth';

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
  const [repositories, setRepositories] = useState<GitHubRepository[]>([]);
  const [branches, setBranches] = useState<GitHubBranch[]>([]);
  const [selectedRepository, setSelectedRepository] = useState<GitHubRepository | null>(null);
  const [selectedBranch, setSelectedBranch] = useState<string>('');
  const [loadingRepos, setLoadingRepos] = useState(false);
  const [loadingBranches, setLoadingBranches] = useState(false);
  const [isRepoDropdownOpen, setIsRepoDropdownOpen] = useState(false);
  const [isBranchDropdownOpen, setIsBranchDropdownOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { sessionToken } = useAuth();

  const loadBranches = useCallback(async () => {
    if (!selectedRepository) return;
    
    setLoadingBranches(true);
    setSelectedBranch('');
    setBranches([]);
    
    try {
      const [owner, repo] = selectedRepository.full_name.split('/');
      const branchList = await ApiService.getRepositoryBranches(owner, repo, sessionToken || undefined);
      setBranches(branchList);
      
      // Auto-select main or master branch if available
      const defaultBranch = branchList.find(b => 
        b.name === 'main' || b.name === 'master'
      );
      if (defaultBranch) {
        setSelectedBranch(defaultBranch.name);
      } else if (branchList.length > 0) {
        setSelectedBranch(branchList[0].name);
      }
    } catch (error) {
      console.error('Failed to load branches:', error);
      setError('Failed to load branches. Please try again.');
    } finally {
      setLoadingBranches(false);
    }
  }, [selectedRepository]);

  // Load repositories when toast opens
  useEffect(() => {
    if (isOpen) {
      loadRepositories();
    }
  }, [isOpen]);

  // Load branches when repository is selected
  useEffect(() => {
    if (selectedRepository) {
      loadBranches();
    }
  }, [selectedRepository, loadBranches]);

  const loadRepositories = async () => {
    setLoadingRepos(true);
    setError(null);
    try {
      const repos = await ApiService.getUserRepositories(sessionToken || undefined);
      setRepositories(repos);
    } catch (error) {
      console.error('Failed to load repositories:', error);
      setError('Failed to load repositories. Please try again.');
    } finally {
      setLoadingRepos(false);
    }
  };

  const handleConfirm = () => {
    if (selectedRepository && selectedBranch) {
      onConfirm({
        repository: selectedRepository,
        branch: selectedBranch
      });
    }
  };

  const handleRepositorySelect = (repo: GitHubRepository) => {
    setSelectedRepository(repo);
    setIsRepoDropdownOpen(false);
  };

  const handleBranchSelect = (branchName: string) => {
    setSelectedBranch(branchName);
    setIsBranchDropdownOpen(false);
  };

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40" />
      
      {/* Toast */}
      <div className="fixed top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 z-50">
        <div className="bg-zinc-800 border border-zinc-700 rounded-xl shadow-2xl p-6 w-[500px] max-w-[90vw]">
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-3">
              <Github className="w-6 h-6 text-primary" />
              <div>
                <h2 className="text-lg font-semibold text-fg">Select Repository</h2>
                <p className="text-sm text-fg/70">Choose a repository and branch to analyze</p>
              </div>
            </div>
            <button
              onClick={onCancel}
              className="p-2 hover:bg-zinc-700 rounded-lg transition-colors"
              aria-label="Cancel"
            >
              <X className="w-5 h-5 text-fg" />
            </button>
          </div>

          {/* Error Message */}
          {error && (
            <div className="mb-4 p-3 bg-error/10 border border-error/30 rounded-lg">
              <p className="text-sm text-error">{error}</p>
            </div>
          )}

          {/* Repository Selection */}
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-fg mb-2">
                Repository
              </label>
              <div className="relative">
                <button
                  onClick={() => setIsRepoDropdownOpen(!isRepoDropdownOpen)}
                  disabled={loadingRepos}
                  className="w-full flex items-center justify-between px-4 py-3 bg-zinc-900 border border-zinc-600 rounded-lg text-fg hover:border-zinc-500 transition-colors disabled:opacity-50"
                >
                  <span className="flex items-center gap-2">
                    {loadingRepos ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Loading repositories...
                      </>
                    ) : selectedRepository ? (
                      <>
                        <Github className="w-4 h-4 text-fg/60" />
                        {selectedRepository.full_name}
                      </>
                    ) : (
                      'Select a repository'
                    )}
                  </span>
                  <ChevronDown className={`w-4 h-4 transition-transform ${isRepoDropdownOpen ? 'rotate-180' : ''}`} />
                </button>
                
                {isRepoDropdownOpen && repositories.length > 0 && (
                  <div className="absolute top-full left-0 right-0 mt-1 bg-zinc-900 border border-zinc-600 rounded-lg shadow-lg max-h-64 overflow-y-auto z-10">
                    {repositories.map((repo) => (
                      <button
                        key={repo.id}
                        onClick={() => handleRepositorySelect(repo)}
                        className="w-full px-4 py-3 text-left hover:bg-zinc-800 transition-colors border-b border-zinc-700 last:border-b-0"
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="text-fg font-medium">{repo.full_name}</p>
                            {repo.description && (
                              <p className="text-fg/60 text-sm truncate">{repo.description}</p>
                            )}
                          </div>
                          <div className="flex items-center gap-2 text-xs text-fg/60">
                            {repo.language && (
                              <span className="px-2 py-1 bg-zinc-700 rounded">{repo.language}</span>
                            )}
                            {repo.private && (
                              <span className="px-2 py-1 bg-amber-600/20 text-amber-400 rounded">Private</span>
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
              <label className="block text-sm font-medium text-fg mb-2">
                Branch
              </label>
              <div className="relative">
                <button
                  onClick={() => setIsBranchDropdownOpen(!isBranchDropdownOpen)}
                  disabled={!selectedRepository || loadingBranches}
                  className="w-full flex items-center justify-between px-4 py-3 bg-zinc-900 border border-zinc-600 rounded-lg text-fg hover:border-zinc-500 transition-colors disabled:opacity-50"
                >
                  <span className="flex items-center gap-2">
                    {loadingBranches ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Loading branches...
                      </>
                    ) : selectedBranch ? (
                      <>
                        <GitBranch className="w-4 h-4 text-fg/60" />
                        {selectedBranch}
                      </>
                    ) : (
                      'Select a branch'
                    )}
                  </span>
                  <ChevronDown className={`w-4 h-4 transition-transform ${isBranchDropdownOpen ? 'rotate-180' : ''}`} />
                </button>
                
                {isBranchDropdownOpen && branches.length > 0 && (
                  <div className="absolute top-full left-0 right-0 mt-1 bg-zinc-900 border border-zinc-600 rounded-lg shadow-lg max-h-48 overflow-y-auto z-10">
                    {branches.map((branch) => (
                      <button
                        key={branch.name}
                        onClick={() => handleBranchSelect(branch.name)}
                        className="w-full px-4 py-3 text-left hover:bg-zinc-800 transition-colors border-b border-zinc-700 last:border-b-0"
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-fg">{branch.name}</span>
                          {branch.protected && (
                            <span className="text-xs text-amber-400">Protected</span>
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
          <div className="flex items-center gap-3 mt-6 pt-4 border-t border-zinc-700">
            <button
              onClick={onCancel}
              className="flex-1 px-4 py-2 text-fg/80 hover:text-fg transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleConfirm}
              disabled={!selectedRepository || !selectedBranch}
              className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-primary hover:bg-primary/80 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
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