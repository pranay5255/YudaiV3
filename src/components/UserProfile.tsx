import React, { useState } from 'react';
import { User, LogOut, ChevronDown, Github, GitBranch, MessageCircle, Plus } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { useRepository } from '../contexts/RepositoryContext';
import { useSession } from '../contexts/SessionContext';

export const UserProfile: React.FC = () => {
  const { user, logout, isLoading } = useAuth();
  const { selectedRepository, clearSelectedRepository } = useRepository();
  const { currentSession, sessions, createNewSession, switchToSession, updateSessionTitle } = useSession();
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [newTitle, setNewTitle] = useState('');

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

              {/* Current Session Information */}
              <div className="mt-3 pt-3 border-t border-zinc-700">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-medium text-fg/70">CURRENT SESSION</span>
                  <button
                    onClick={() => {
                      const sessionId = createNewSession();
                      switchToSession(sessionId);
                    }}
                    className="text-xs text-fg/50 hover:text-fg/70 transition-colors flex items-center gap-1"
                  >
                    <Plus className="w-3 h-3" />
                    New
                  </button>
                </div>
                
                {currentSession ? (
                  <div className="p-2 bg-zinc-700/50 rounded">
                    <div className="flex items-center gap-2">
                      <MessageCircle className="w-4 h-4 text-primary" />
                      <div className="flex-1 min-w-0">
                        {isEditingTitle ? (
                          <input
                            type="text"
                            value={newTitle}
                            onChange={(e) => setNewTitle(e.target.value)}
                            onBlur={async () => {
                              if (newTitle.trim() && newTitle !== currentSession.title) {
                                try {
                                  await updateSessionTitle(currentSession.session_id, newTitle);
                                } catch (err) {
                                  console.error('Failed to update title:', err);
                                }
                              }
                              setIsEditingTitle(false);
                            }}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') {
                                e.currentTarget.blur();
                              }
                            }}
                            className="text-xs font-medium text-fg bg-transparent border-none outline-none w-full"
                            autoFocus
                          />
                        ) : (
                          <p 
                            className="text-xs font-medium text-fg truncate cursor-pointer"
                            onClick={() => {
                              setNewTitle(currentSession.title || '');
                              setIsEditingTitle(true);
                            }}
                          >
                            {currentSession.title || `Session ${currentSession.session_id.slice(0, 8)}...`}
                          </p>
                        )}
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="text-xs text-fg/60">
                            {currentSession.total_messages} messages
                          </span>
                          <span className="text-xs text-fg/60">•</span>
                          <span className="text-xs text-fg/60">
                            {currentSession.total_tokens} tokens
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="p-2 bg-zinc-700/50 rounded">
                    <p className="text-xs text-fg/50">No active session</p>
                    <p className="text-xs text-fg/40">Start chatting to create one</p>
                  </div>
                )}
                
                {/* Recent Sessions */}
                {sessions.length > 0 && (
                  <div className="mt-2">
                    <p className="text-xs font-medium text-fg/70 mb-1">RECENT SESSIONS</p>
                    <div className="space-y-1 max-h-32 overflow-y-auto">
                      {sessions.slice(0, 3).map((session) => (
                        <button
                          key={session.session_id}
                          onClick={() => switchToSession(session.session_id)}
                          className={`w-full text-left p-1.5 rounded text-xs transition-colors ${
                            currentSession?.session_id === session.session_id
                              ? 'bg-primary/20 text-primary'
                              : 'hover:bg-zinc-600/50 text-fg/70'
                          }`}
                        >
                          <div className="truncate">
                            {session.title || `Session ${session.session_id.slice(0, 8)}...`}
                          </div>
                          <div className="text-xs text-fg/50 mt-0.5">
                            {session.total_messages} messages
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
              
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