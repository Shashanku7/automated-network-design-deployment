/**
 * TopBar — Header bar (persistent across all pages)
 *
 * Contains: "NetOrch OS" branding (links to dashboard), search, and user actions.
 */

import { useState, useEffect, useRef } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useProject } from "../context/ProjectContext";

export default function TopBar() {
  const navigate = useNavigate();
  const { getProjectList } = useProject();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [showResults, setShowResults] = useState(false);
  const searchRef = useRef(null);

  useEffect(() => {
    if (query.length > 1) {
      const projects = getProjectList();
      const filtered = projects.filter((p) =>
        p.title.toLowerCase().includes(query.toLowerCase()),
      );
      setResults(filtered);
      setShowResults(true);
    } else {
      setShowResults(false);
    }
  }, [query, getProjectList]);

  // Close search when clicking outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (searchRef.current && !searchRef.current.contains(e.target)) {
        setShowResults(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleResultClick = (id) => {
    setShowResults(false);
    setQuery("");
    navigate(`/project/${id}`);
  };

  return (
    <header className="flex justify-between items-center px-6 w-full sticky top-0 z-50 h-14 bg-surface border-b border-outline-variant/15 shrink-0">
      <div className="flex items-center gap-6">
        <NavLink
          to="/"
          className="flex items-center gap-3 group cursor-pointer"
        >
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary to-primary-container flex items-center justify-center group-hover:scale-105 transition-transform">
            <span className="material-symbols-outlined text-sm text-on-primary">
              hub
            </span>
          </div>
          <div className="hidden sm:block">
            <div className="text-sm font-bold text-on-surface group-hover:text-primary transition-colors leading-tight">
              NetOrch
            </div>
            <div className="text-[10px] text-on-surface/60 uppercase tracking-wider leading-tight">
              Network Architect
            </div>
          </div>
        </NavLink>

        {/* Search Bar with Results Dropdown */}
        <div className="relative flex items-center" ref={searchRef}>
          <span className="material-symbols-outlined absolute left-3 text-outline text-sm">
            search
          </span>
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
                <span className="text-[10px] font-bold text-outline uppercase tracking-widest px-2">
                  Projects
                </span>
              </div>
              <div className="max-h-64 overflow-y-auto">
                {results.length > 0 ? (
                  results.map((project) => (
                    <button
                      key={project.id}
                      onClick={() => handleResultClick(project.id)}
                      className="w-full flex items-center justify-between px-4 py-3 hover:bg-primary/10 text-left transition-colors group"
                    >
                      <div className="flex flex-col">
                        <span className="text-sm font-medium text-on-surface group-hover:text-primary transition-colors">
                          {project.title}
                        </span>
                        <span className="text-[10px] text-on-surface-variant uppercase tracking-wider">
                          {project.status || "draft"}
                        </span>
                      </div>
                      <span className="material-symbols-outlined text-outline group-hover:text-primary text-sm opacity-0 group-hover:opacity-100 transition-all">
                        open_in_new
                      </span>
                    </button>
                  ))
                ) : (
                  <div className="p-4 text-center">
                    <p className="text-sm text-on-surface-variant">
                      No projects found for "{query}"
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="flex items-center gap-4">
        <button
          onClick={() => window.alert("Notifications feature coming soon!")}
          className="p-2 text-on-surface/70 hover:bg-surface-container-high transition-colors rounded-full"
        >
          <span className="material-symbols-outlined">notifications</span>
        </button>
        <button
          onClick={() => window.alert("Settings feature coming soon!")}
          className="p-2 text-on-surface/70 hover:bg-surface-container-high transition-colors rounded-full"
        >
          <span className="material-symbols-outlined">settings</span>
        </button>
        <div
          onClick={() => window.alert("User Profile feature coming soon!")}
          className="h-8 w-8 rounded-full bg-primary-container flex items-center justify-center text-on-primary text-sm font-bold cursor-pointer hover:brightness-110 transition-all"
        >
          U
        </div>
      </div>
    </header>
  );
}
