import React, { useEffect, useState } from 'react';
import { ApiService } from '../services/api';
import { IssueCategory, IssueConfig } from '../types';

const ISSUE_CATEGORIES: IssueCategory[] = [
  'Bug-fix',
  'Add-library',
  'add-tests(pytest)',
  'add-tests(docker)',
  'new-feature-scaffold',
  'refactor',
  'docs update',
  'context-update(md files)',
  'containerisation',
  'database-design(sqlAlchemy+pydantic)',
  'type-setting(pydantic)',
  'type-setting(typescript)'
];

interface IssueSetupProps {
  onComplete: (config: IssueConfig) => void;
}

export const IssueSetup: React.FC<IssueSetupProps> = ({ onComplete }) => {
  const [repos, setRepos] = useState<any[]>([]);
  const [selectedRepo, setSelectedRepo] = useState('');
  const [branches, setBranches] = useState<string[]>([]);
  const [selectedBranch, setSelectedBranch] = useState('');
  const [selectedTypes, setSelectedTypes] = useState<IssueCategory[]>([]);
  const [loadingRepos, setLoadingRepos] = useState(true);

  useEffect(() => {
    const fetchRepos = async () => {
      try {
        const data = await ApiService.getRepositories();
        setRepos(data);
      } catch (err) {
        console.error('Failed to load repositories', err);
      } finally {
        setLoadingRepos(false);
      }
    };

    fetchRepos();
  }, []);

  useEffect(() => {
    if (!selectedRepo) return;
    const [owner, repo] = selectedRepo.split('/');

    const fetchBranches = async () => {
      try {
        const response = await fetch(`https://api.github.com/repos/${owner}/${repo}/branches`, {
          headers: {
            Authorization: `Bearer ${localStorage.getItem('auth_token')}`
          }
        });
        if (response.ok) {
          const data = await response.json();
          const branchNames = data.map((b: any) => b.name);
          setBranches(branchNames);
          setSelectedBranch(branchNames[0] || '');
        }
      } catch (err) {
        console.error('Failed to load branches', err);
      }
    };

    fetchBranches();
  }, [selectedRepo]);

  const handleCategoryChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const opts = Array.from(e.target.selectedOptions).map(o => o.value as IssueCategory);
    setSelectedTypes(opts);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedRepo || !selectedBranch) return;
    const [owner, repo] = selectedRepo.split('/');
    const config: IssueConfig = {
      repoOwner: owner,
      repoName: repo,
      branch: selectedBranch,
      categories: selectedTypes
    };
    onComplete(config);
  };

  return (
    <div className="p-6 space-y-4">
      <h2 className="text-xl font-semibold text-fg">Project Setup</h2>
      {loadingRepos ? (
        <p className="text-fg">Loading repositories...</p>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm mb-1">Repository</label>
            <select
              value={selectedRepo}
              onChange={e => setSelectedRepo(e.target.value)}
              className="bg-zinc-800 border border-zinc-700 rounded-lg p-2 w-full"
            >
              <option value="">Select repository</option>
              {repos.map(r => (
                <option key={r.full_name} value={r.full_name}>
                  {r.full_name}
                </option>
              ))}
            </select>
          </div>

          {branches.length > 0 && (
            <div>
              <label className="block text-sm mb-1">Branch</label>
              <select
                value={selectedBranch}
                onChange={e => setSelectedBranch(e.target.value)}
                className="bg-zinc-800 border border-zinc-700 rounded-lg p-2 w-full"
              >
                {branches.map(b => (
                  <option key={b} value={b}>
                    {b}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div>
            <label className="block text-sm mb-1">Issue Types</label>
            <select
              multiple
              value={selectedTypes}
              onChange={handleCategoryChange}
              className="bg-zinc-800 border border-zinc-700 rounded-lg p-2 w-full h-32"
            >
              {ISSUE_CATEGORIES.map(c => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>

          <button
            type="submit"
            className="bg-primary hover:bg-primary/80 text-white px-4 py-2 rounded-lg"
          >
            Start Chat
          </button>
        </form>
      )}
    </div>
  );
};
