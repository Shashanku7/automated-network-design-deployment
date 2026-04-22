/**
 * Dashboard — Home / Project Overview
 * 
 * Shows project metrics, recent projects table,
 * quick actions, and system status.
 * Uses user-friendly project names (not engineering terms).
 */

import { useNavigate } from 'react-router-dom';
import { useProject } from '../context/ProjectContext';

// Sample projects with user-friendly names (not engineering jargon)
const recentProjects = [
  { name: 'Main Campus Network', id: 'PROJ-001', status: 'Designing', statusColor: 'bg-primary', time: '2h ago' },
  { name: 'Hostel Block Wi-Fi', id: 'PROJ-002', status: 'Deployed', statusColor: 'bg-tertiary', time: 'Yesterday' },
  { name: 'Library & Lab Setup', id: 'PROJ-003', status: 'Ready', statusColor: 'bg-primary-container', time: 'Oct 24' },
  { name: 'Admin Office Network', id: 'PROJ-004', status: 'Designing', statusColor: 'bg-primary', time: 'Oct 21' },
];

const metrics = [
  { label: 'Total Projects', value: '12', icon: 'folder_special', accent: 'primary' },
  { label: 'Active Deployments', value: '4', icon: 'rocket_launch', accent: 'tertiary' },
  { label: 'Network Health', value: 'Optimal', icon: 'monitor_heart', accent: 'primary' },
  { label: 'Pending Reviews', value: '03', icon: 'assignment_late', accent: 'error' },
];

export default function Dashboard() {
  const navigate = useNavigate();
  const { dispatch } = useProject();

  function handleNewDesign() {
    dispatch({ type: 'RESET_PROJECT' });
    navigate('/solution-type');
  }

  return (
    <div className="h-full overflow-y-auto p-8 space-y-8 custom-scrollbar">
      {/* Header */}
      <section className="flex justify-between items-end">
        <div>
          <h1 className="text-3xl font-bold font-[family-name:var(--font-headline)] text-on-surface">Network Hub</h1>
          <p className="text-on-surface-variant mt-1">Overview of your network design projects.</p>
        </div>
        <div className="px-4 py-2 bg-surface-container-low rounded-md border border-outline-variant/15 flex items-center gap-2">
          <span className="material-symbols-outlined text-tertiary text-lg">check_circle</span>
          <span className="text-sm font-medium">System Online</span>
        </div>
      </section>

      {/* Metrics Cards */}
      <section className="grid grid-cols-1 md:grid-cols-4 gap-6">
        {metrics.map(m => (
          <div key={m.label} className="bg-surface-container-low p-6 rounded-xl border border-outline-variant/15 relative overflow-hidden group">
            <div className="flex justify-between items-start mb-4">
              <div className={`p-2 bg-${m.accent}/10 rounded-lg`}>
                <span className={`material-symbols-outlined text-${m.accent}`}>{m.icon}</span>
              </div>
            </div>
            <div className="text-3xl font-bold font-[family-name:var(--font-headline)]">{m.value}</div>
            <div className="text-sm text-on-surface-variant font-medium">{m.label}</div>
            <div className="absolute -right-4 -bottom-4 opacity-5 group-hover:opacity-10 transition-opacity">
              <span className="material-symbols-outlined text-8xl">{m.icon}</span>
            </div>
          </div>
        ))}
      </section>

      {/* Main Grid: Projects + Quick Actions */}
      <section className="grid grid-cols-1 lg:grid-cols-3 gap-8 pb-12">
        {/* Recent Projects Table */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex justify-between items-center px-2">
            <h2 className="text-xl font-bold font-[family-name:var(--font-headline)] flex items-center gap-2">
              <span className="material-symbols-outlined text-primary">history</span>
              Recent Projects
            </h2>
            <button className="text-primary text-sm font-medium hover:underline">View All</button>
          </div>
          <div className="bg-surface-container-low rounded-xl border border-outline-variant/15 overflow-hidden">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-surface-container/50 border-b border-outline-variant/10">
                  <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider text-outline">Project Name</th>
                  <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider text-outline">Status</th>
                  <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider text-outline">Last Modified</th>
                  <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider text-outline text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant/5">
                {recentProjects.map(p => (
                  <tr key={p.id} className="hover:bg-surface-container transition-colors">
                    <td className="px-6 py-4">
                      <div className="font-medium text-on-surface">{p.name}</div>
                      <div className="text-xs text-outline font-[family-name:var(--font-mono)]">ID: {p.id}</div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <div className={`w-1.5 h-1.5 rounded-full ${p.statusColor} shadow-lg`} />
                        <span className="text-sm font-medium">{p.status}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-on-surface-variant">{p.time}</td>
                    <td className="px-6 py-4 text-right">
                      <button className="p-2 text-outline hover:text-primary transition-colors">
                        <span className="material-symbols-outlined">edit</span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="space-y-6">
          <div className="space-y-4">
            <h2 className="text-xl font-bold font-[family-name:var(--font-headline)] flex items-center gap-2 px-2">
              <span className="material-symbols-outlined text-primary">bolt</span>
              Quick Actions
            </h2>
            <div className="flex flex-col gap-3">
              <button onClick={handleNewDesign} className="flex items-center justify-between p-4 bg-gradient-to-br from-primary to-primary-container text-on-primary rounded-xl font-bold hover:brightness-110 transition-all group">
                <span className="flex items-center gap-3">
                  <span className="material-symbols-outlined">add_circle</span>
                  Start New Design
                </span>
                <span className="material-symbols-outlined group-hover:translate-x-1 transition-transform">arrow_forward</span>
              </button>
              <button 
                onClick={() => window.open('https://www.arubanetworks.com/techdocs/central/latest/content/home.htm', '_blank')}
                className="flex items-center justify-between p-4 bg-surface-container-low border border-outline-variant/15 text-on-surface rounded-xl font-medium hover:bg-surface-container-high transition-all group"
              >
                <span className="flex items-center gap-3">
                  <span className="material-symbols-outlined text-primary">menu_book</span>
                  View Documentation
                </span>
                <span className="material-symbols-outlined text-outline group-hover:translate-x-1 transition-transform">open_in_new</span>
              </button>
            </div>
          </div>

          {/* Recent Design Events — Much clearer than a generic chart */}
          <div className="bg-surface-container-low rounded-xl border border-outline-variant/15 p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-bold font-[family-name:var(--font-headline)]">Recent Design Events</h3>
              <span className="material-symbols-outlined text-primary">history_edu</span>
            </div>
            <div className="space-y-4">
              {[
                { event: 'Topology Generated', project: 'Main Campus', time: '12 mins ago', icon: 'hub' },
                { event: 'BOM Exported', project: 'Hostel Wi-Fi', time: '45 mins ago', icon: 'file_download' },
                { event: 'Requirements Saved', project: 'Library Setup', time: '2 hours ago', icon: 'save' },
                { event: 'Deployment Started', project: 'Admin Office', time: '3 hours ago', icon: 'rocket_launch' },
              ].map((e, i) => (
                <div key={i} className="flex items-center gap-3 group cursor-default">
                  <div className="w-8 h-8 rounded bg-surface-container-high flex items-center justify-center text-outline group-hover:text-primary transition-colors">
                    <span className="material-symbols-outlined text-sm">{e.icon}</span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-[11px] font-bold text-on-surface truncate">{e.event}</div>
                    <div className="text-[10px] text-on-surface-variant truncate">{e.project}</div>
                  </div>
                  <div className="text-[9px] text-outline font-medium whitespace-nowrap">{e.time}</div>
                </div>
              ))}
            </div>
            <button className="w-full py-2 border border-outline-variant/10 rounded text-[10px] font-bold text-on-surface-variant hover:bg-surface-container-high transition-colors uppercase tracking-wider">
              View Full History
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
