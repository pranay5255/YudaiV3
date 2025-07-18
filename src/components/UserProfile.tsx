import React, { useState } from 'react';
import { User, LogOut, ChevronDown, Github, GitBranch } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useRepository } from '../contexts/RepositoryContext';

export const UserProfile: React.FC = () => {
  const { user, logout, isLoading } = useAuth();
  const { selectedRepository, clearSelectedRepository } = useRepository();
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  const handleLogout = async () => {
    try {
      setIsLoggingOut(true);
      await logout();
    } catch (error) {
      console.error('Logout failed:', error);
      setIsLoggingOut(false);
    }
  };

  if (!user) {
    return null;
  }

  // Use display_name if available, fallback to github_username
  const displayName = user.display_name || user.github_username;
  const username = user.github_username;

  return (
    <div className="relative">
      <button
        onClick={() => setIsDropdownOpen(!isDropdownOpen)}
        className="flex items-center space-x-2 text-fg hover:text-primary transition-colors duration-200 bg-zinc-800/50 hover:bg-zinc-800 rounded-lg px-3 py-2"
      >
        {user.avatar_url ? (
          <img
            src={user.avatar_url}
            alt={username}
            className="w-6 h-6 rounded-full"
          />
        ) : (
          <User className="w-5 h-5" />
        )}
        <span className="text-sm font-medium">{username}</span>
        <ChevronDown className={`w-4 h-4 transition-transform duration-200 ${
          isDropdownOpen ? 'rotate-180' : ''
        }`} />
      </button>

      {isDropdownOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-10"
            onClick={() => setIsDropdownOpen(false)}
          />
          
          {/* Dropdown Menu */}
          <div className="absolute right-0 mt-2 w-72 bg-zinc-800 border border-zinc-700 rounded-lg shadow-lg z-20">
            <div className="p-4 border-b border-zinc-700">
              <div className="flex items-center space-x-3">
                {user.avatar_url ? (
                  <img
                    src={user.avatar_url}
                    alt={username}
                    className="w-12 h-12 rounded-full"
                  />
                ) : (
                  <div className="w-12 h-12 bg-primary rounded-full flex items-center justify-center">
                    <User className="w-6 h-6 text-white" />
                  </div>
                )}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-fg truncate">
                    {displayName}
                  </p>
                  <p className="text-xs text-fg/80 truncate">
                    @{username}
                  </p>
                  {user.email && (
                    <p className="text-xs text-fg/70 truncate mt-1">
                      {user.email}
                    </p>
                  )}
                </div>
              </div>
              
              {/* Selected Repository Information */}
              {selectedRepository && (
                <div className="mt-3 pt-3 border-t border-zinc-700">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-medium text-fg/70">ACTIVE REPOSITORY</span>
                    <button
                      onClick={clearSelectedRepository}
                      className="text-xs text-fg/50 hover:text-fg/70 transition-colors"
                    >
                      Clear
                    </button>
                  </div>
                  <div className="flex items-center gap-2 p-2 bg-zinc-700/50 rounded">
                    <Github className="w-4 h-4 text-primary" />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-fg truncate">
                        {selectedRepository.repository.full_name}
                      </p>
                      <div className="flex items-center gap-1 mt-0.5">
                        <GitBranch className="w-3 h-3 text-fg/60" />
                        <span className="text-xs text-fg/60">{selectedRepository.branch}</span>
                      </div>
                    </div>
                  </div>
                </div>
              )}
              
              {/* Additional Profile Information */}
              <div className="mt-3 pt-3 border-t border-zinc-700">
                <div className="grid grid-cols-1 gap-2 text-xs">
                  <div className="flex justify-between">
                    <span className="text-fg/70">GitHub ID:</span>
                    <span className="text-fg/90">{user.github_user_id}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-fg/70">Member since:</span>
                    <span className="text-fg/90">
                      {new Date(user.created_at).toLocaleDateString()}
                    </span>
                  </div>
                  {user.last_login && (
                    <div className="flex justify-between">
                      <span className="text-fg/70">Last login:</span>
                      <span className="text-fg/90">
                        {new Date(user.last_login).toLocaleDateString()}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div className="p-2">
              <button
                onClick={handleLogout}
                disabled={isLoading || isLoggingOut}
                className="w-full flex items-center space-x-2 px-3 py-2 text-sm text-fg hover:bg-zinc-700 rounded-md transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isLoggingOut ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-current" />
                    <span>Signing out...</span>
                  </>
                ) : (
                  <>
                    <LogOut className="w-4 h-4" />
                    <span>Sign out</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}; 