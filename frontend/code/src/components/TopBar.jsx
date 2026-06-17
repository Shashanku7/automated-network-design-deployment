/**
 * TopBar — Header bar (persistent across all pages)
 * 
 * Contains: "NetOrch OS" branding (links to dashboard), search, and user actions.
 */

import { useState, useEffect, useRef } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';

const MOCK_PROJECTS = [
  { id: '1', name: 'Campus Core Refresh', type: 'Campus' },
  { id: '2', name: 'Data Center West', type: 'Data Center' },
  { id: '3', name: 'Remote Office VPN', type: 'SD-WAN' },
  { id: '4', name: 'IoT Security Layer', type: 'Security' },
];
// TODO: Replace MOCK_PROJECTS with localStorage lookup (step 7)

// TODO: [BACKEND TEAM]
// Replace 'MOCK_PROJECTS' with a real API call.
// Implementation: Create a debounced function that calls GET /api/projects?search=${query}
// and populates the results state dynamically.

export default function TopBar() {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [showResults, setShowResults] = useState(false);
  const searchRef = useRef(null);

  // Simple search logic
  useEffect(() => {
    if (query.length > 1) {
      const filtered = MOCK_PROJECTS.filter(p => 
        p.name.toLowerCase().includes(query.toLowerCase())
      );
      setResults(filtered);
      setShowResults(true);
    } else {
      setShowResults(false);
    }
  }, [query]);

  // Close search when clicking outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (searchRef.current && !searchRef.current.contains(e.target)) {
        setShowResults(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleResultClick = (id) => {
    setShowResults(false);
    setQuery('');
    navigate(`/project/${id}`);
  };

  return (
    <header className="flex justify-between items-center px-6 w-full sticky top-0 z-50 h-14 bg-surface border-b border-outline-variant/15 shrink-0">
      <div className="flex items-center gap-6">
        <NavLink to="/" className="text-lg font-bold text-primary font-[family-name:var(--font-headline)] hover:opacity-80 transition-opacity">
          NetOrch
        </NavLink>
        
        {/* Search Bar with Results Dropdown */}
        <div className="relative flex items-center ml-4" ref={searchRef}>
          <span className="material-symbols-outlined absolute left-3 text-outline text-sm">search</span>
          <input
            className="bg-surface-container-low border-none rounded-md py-1.5 pl-10 pr-4 text-sm w-80 focus:ring-1 focus:ring-primary text-on-surface placeholder:text-outline/50 transition-all focus:w-96"
            placeholder="Search projects..."
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => query.length > 1 && setShowResults(true)}
          />

          {/* Floating Search Results */}
          {showResults && (
            <div className="absolute top-full left-0 w-full mt-2 bg-surface-container-high border border-outline-variant/30 rounded-xl shadow-2xl overflow-hidden animate-in fade-in slide-in-from-top-2 duration-200">
              <div className="p-2 border-b border-outline-variant/10">
                <span className="text-[10px] font-bold text-outline uppercase tracking-widest px-2">Projects</span>
              </div>
              <div className="max-h-64 overflow-y-auto">
                {results.length > 0 ? (
                  results.map(project => (
                    <button
                      key={project.id}
                      onClick={() => handleResultClick(project.id)}
                      className="w-full flex items-center justify-between px-4 py-3 hover:bg-primary/10 text-left transition-colors group"
                    >
                      <div className="flex flex-col">
                        <span className="text-sm font-medium text-on-surface group-hover:text-primary transition-colors">{project.name}</span>
                        <span className="text-[10px] text-on-surface-variant uppercase tracking-wider">{project.type}</span>
                      </div>
                      <span className="material-symbols-outlined text-outline group-hover:text-primary text-sm opacity-0 group-hover:opacity-100 transition-all">open_in_new</span>
                    </button>
                  ))
                ) : (
                  <div className="p-4 text-center">
                    <p className="text-sm text-on-surface-variant">No projects found for "{query}"</p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="flex items-center gap-4">
        <button 
          onClick={() => window.alert('Notifications feature coming soon!')}
          className="p-2 text-on-surface/70 hover:bg-surface-container-high transition-colors rounded-full"
        >
          <span className="material-symbols-outlined">notifications</span>
        </button>
        <button 
          onClick={() => window.alert('Settings feature coming soon!')}
          className="p-2 text-on-surface/70 hover:bg-surface-container-high transition-colors rounded-full"
        >
          <span className="material-symbols-outlined">settings</span>
        </button>
        <div 
          onClick={() => window.alert('User Profile feature coming soon!')}
          className="h-8 w-8 rounded-full bg-primary-container flex items-center justify-center text-on-primary text-sm font-bold cursor-pointer hover:brightness-110 transition-all"
        >
          U
        </div>
      </div>
    </header>
  );
}
