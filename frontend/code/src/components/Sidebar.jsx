/**
 * Sidebar — Left navigation panel (persistent across all pages)
 * 
 * Contains:
 * - Project identity (clickable → dashboard)
 * - Navigation links (Dashboard, Requirements, Design, Deployment)
 * - "New Design" CTA button
 */

import { NavLink, useNavigate } from 'react-router-dom';
import { useProject } from '../context/ProjectContext';

const navItems = [
  { path: '/',            icon: 'dashboard',     label: 'Dashboard' },
  { path: '/requirements',icon: 'list_alt',      label: 'Requirements' },
  { path: '/design',      icon: 'hub',           label: 'Design' },
  { path: '/deployment',  icon: 'rocket_launch', label: 'Deployment' },
];

export default function Sidebar() {
  const navigate = useNavigate();
  const { dispatch } = useProject();

  function handleNewDesign() {
    dispatch({ type: 'RESET_PROJECT' });
    navigate('/solution-type');
  }

  return (
    <aside className="flex flex-col fixed left-0 top-0 h-full z-40 w-64 border-r border-outline-variant/15 bg-surface-dim font-body text-sm font-medium">
      <div className="p-6 flex flex-col h-full">

        {/* Project Identity — Clicking goes to Dashboard */}
        <NavLink to="/" className="flex items-center gap-3 mb-8 group cursor-pointer">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary to-primary-container flex items-center justify-center group-hover:scale-105 transition-transform">
            <span className="material-symbols-outlined text-on-primary">hub</span>
          </div>
          <div>
            <div className="text-on-surface font-bold group-hover:text-primary transition-colors">Project Core</div>
            <div className="text-on-surface/60 text-xs uppercase tracking-wider">Network Architect</div>
          </div>
        </NavLink>

        {/* Navigation Links */}
        <nav className="flex flex-col gap-1">
          {navItems.map(item => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-3 rounded-md transition-all ${
                  isActive
                    ? 'text-primary border-r-2 border-primary bg-gradient-to-r from-primary/10 to-transparent font-bold'
                    : 'text-on-surface/60 hover:text-on-surface hover:bg-surface'
                }`
              }
            >
              <span className="material-symbols-outlined">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>

        {/* Bottom section */}
        <div className="mt-auto space-y-4">
          {/* New Design CTA */}
          <button
            onClick={handleNewDesign}
            className="w-full bg-gradient-to-br from-primary to-primary-container text-on-primary font-bold py-2.5 rounded-md flex items-center justify-center gap-2 hover:brightness-110 transition-all active:scale-[0.98]"
          >
            <span className="material-symbols-outlined text-lg">add</span>
            New Design
          </button>

          {/* Footer links */}
          <button 
            onClick={() => window.open('https://www.arubanetworks.com/techdocs/central/latest/content/home.htm', '_blank')}
            className="w-full flex items-center gap-3 px-3 py-2 text-on-surface/60 hover:text-on-surface transition-all text-left"
          >
            <span className="material-symbols-outlined text-xl">description</span>
            Documentation
          </button>
          <button 
            onClick={() => window.open('https://networkingsupport.hpe.com', '_blank')}
            className="w-full flex items-center gap-3 px-3 py-2 text-on-surface/60 hover:text-on-surface transition-all text-left"
          >
            <span className="material-symbols-outlined text-xl">help</span>
            Support
          </button>
        </div>
      </div>
    </aside>
  );
}
