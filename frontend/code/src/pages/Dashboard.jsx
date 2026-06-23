import { useEffect, useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useProject } from "../context/ProjectContext";

const statusStyles = {
  draft: "bg-surface-container-high text-on-surface-variant",
  designing: "bg-primary/10 text-primary",
  complete: "bg-tertiary/10 text-tertiary",
  deployed: "bg-tertiary/10 text-tertiary",
};

function statusLabel(meta) {
  if (!meta) return "draft";
  if (meta.status === "draft") return "Draft";
  if (meta.status === "designing") return "Designing";
  if (meta.status === "deployed") return "Deployed";
  if (meta.status === "complete") return "Complete";
  return "Designing";
}

function timeAgo(dateStr) {
  if (!dateStr) return "";
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(dateStr).toLocaleDateString();
}

function ProjectListView() {
  const navigate = useNavigate();
  const { getProjectList } = useProject();
  const projects = getProjectList();

  const metrics = useMemo(
    () => [
      {
        label: "Total Projects",
        value: projects.length.toString(),
        icon: "folder_special",
        accent: "primary",
      },
      {
        label: "Active Deployments",
        value: projects
          .filter((p) => p.status === "deployed")
          .length.toString(),
        icon: "rocket_launch",
        accent: "tertiary",
      },
      {
        label: "In Design",
        value: projects
          .filter((p) => p.status === "designing" || p.status === "draft")
          .length.toString(),
        icon: "hub",
        accent: "primary",
      },
      {
        label: "Complete",
        value: projects
          .filter((p) => p.status === "complete")
          .length.toString(),
        icon: "check_circle",
        accent: "tertiary",
      },
    ],
    [projects],
  );

  if (projects.length === 0) {
    return (
      <div className="h-full flex flex-col items-center justify-center gap-6 p-8">
        <span className="material-symbols-outlined text-8xl text-outline/30">
          folder_special
        </span>
        <div className="text-center">
          <h2 className="text-2xl font-bold text-on-surface mb-2">
            No projects yet
          </h2>
          <p className="text-on-surface-variant mb-6">
            Create your first network design project to get started.
          </p>
          <button
            onClick={() => navigate("/project/new")}
            className="px-6 py-3 bg-primary text-on-primary font-bold rounded-lg hover:brightness-110 transition-all flex items-center gap-2 mx-auto"
          >
            <span className="material-symbols-outlined text-lg">
              add_circle
            </span>
            Start New Design
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-8 space-y-8 custom-scrollbar">
      <section className="flex justify-between items-end">
        <div>
          <h1 className="text-3xl font-bold font-[family-name:var(--font-headline)] text-on-surface">
            Your Projects
          </h1>
          <p className="text-on-surface-variant mt-1">
            {projects.length} project{projects.length !== 1 ? "s" : ""} total
          </p>
        </div>
        <div className="px-4 py-2 bg-surface-container-low rounded-md border border-outline-variant/15 flex items-center gap-2">
          <span className="material-symbols-outlined text-tertiary text-lg">
            check_circle
          </span>
          <span className="text-sm font-medium">System Online</span>
        </div>
      </section>

      <section className="grid grid-cols-2 md:grid-cols-4 gap-6">
        {metrics.map((m) => (
          <div
            key={m.label}
            className="bg-surface-container-low p-6 rounded-xl border border-outline-variant/15 relative overflow-hidden group"
          >
            <div className="flex justify-between items-start mb-4">
              <div className={`p-2 bg-${m.accent}/10 rounded-lg`}>
                <span className={`material-symbols-outlined text-${m.accent}`}>
                  {m.icon}
                </span>
              </div>
            </div>
            <div className="text-3xl font-bold font-[family-name:var(--font-headline)]">
              {m.value}
            </div>
            <div className="text-sm text-on-surface-variant font-medium">
              {m.label}
            </div>
          </div>
        ))}
      </section>

      <section className="grid grid-cols-1 lg:grid-cols-3 gap-8 pb-12">
        <div className="lg:col-span-2 space-y-4">
          <div className="flex justify-between items-center px-2">
            <h2 className="text-xl font-bold font-[family-name:var(--font-headline)] flex items-center gap-2">
              <span className="material-symbols-outlined text-primary">
                history
              </span>
              Recent Projects
            </h2>
          </div>
          <div className="bg-surface-container-low rounded-xl border border-outline-variant/15 overflow-hidden">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-surface-container/50 border-b border-outline-variant/10">
                  <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider text-outline">
                    Project Name
                  </th>
                  <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider text-outline">
                    Status
                  </th>
                  <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider text-outline">
                    Last Modified
                  </th>
                  <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider text-outline text-right">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant/5">
                {projects.map((p) => (
                  <tr
                    key={p.id}
                    className="hover:bg-surface-container transition-colors cursor-pointer"
                    onClick={() => navigate(`/project/${p.id}`)}
                  >
                    <td className="px-6 py-4">
                      <div className="font-medium text-on-surface">
                        {p.title}
                      </div>
                      <div className="text-xs text-outline font-[family-name:var(--font-mono)]">
                        ID: {p.id.slice(0, 8)}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <span
                          className={`text-sm font-medium px-2 py-0.5 rounded-full ${statusStyles[p.status] || statusStyles.draft}`}
                        >
                          {statusLabel(p)}
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-on-surface-variant">
                      {timeAgo(p.updatedAt)}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(`/project/${p.id}`);
                        }}
                        className="p-2 text-outline hover:text-primary transition-colors"
                      >
                        <span className="material-symbols-outlined">
                          arrow_forward
                        </span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="space-y-6">
          <div className="space-y-4">
            <h2 className="text-xl font-bold font-[family-name:var(--font-headline)] flex items-center gap-2 px-2">
              <span className="material-symbols-outlined text-primary">
                bolt
              </span>
              Quick Actions
            </h2>
            <div className="grid grid-cols-2 lg:flex lg:flex-col gap-3">
              <button
                onClick={() => navigate("/project/new")}
                className="flex items-center justify-between p-4 bg-gradient-to-br from-primary to-primary-container text-on-primary rounded-xl font-bold hover:brightness-110 transition-all group"
              >
                <span className="flex items-center gap-3">
                  <span className="material-symbols-outlined">add_circle</span>
                  Start New Design
                </span>
                <span className="material-symbols-outlined group-hover:translate-x-1 transition-transform">
                  arrow_forward
                </span>
              </button>
              <button
                onClick={() =>
                  window.open(
                    "https://www.arubanetworks.com/techdocs/central/latest/content/home.htm",
                    "_blank",
                  )
                }
                className="flex items-center justify-between p-4 bg-surface-container-low border border-outline-variant/15 text-on-surface rounded-xl font-medium hover:bg-surface-container-high transition-all group"
              >
                <span className="flex items-center gap-3">
                  <span className="material-symbols-outlined text-primary">
                    menu_book
                  </span>
                  View Documentation
                </span>
                <span className="material-symbols-outlined text-outline group-hover:translate-x-1 transition-transform">
                  open_in_new
                </span>
              </button>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

function ProjectDashboardView({ projectId, meta }) {
  const navigate = useNavigate();
  const { state, loadProject, getProjectList } = useProject();

  useEffect(() => {
    loadProject(projectId);
  }, [projectId, loadProject]);

  const status =
    state.workflowStatus === "complete"
      ? "Complete"
      : state.workflowStatus === "running" ||
          state.workflowStatus === "awaiting_approval"
        ? "In Progress"
        : state.requirements?.buildings?.length || state.requirements?.dcRacks
          ? "Requirements Set"
          : state.solutionType
            ? "Solution Chosen"
            : "New";

  return (
    <div className="h-full overflow-y-auto p-8 space-y-8 custom-scrollbar">
      <section className="flex justify-between items-end">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <button
              onClick={() => navigate("/")}
              className="text-outline hover:text-primary transition-colors"
            >
              <span className="material-symbols-outlined">arrow_back</span>
            </button>
            <h1 className="text-3xl font-bold font-[family-name:var(--font-headline)] text-on-surface">
              {state.projectTitle || meta?.title || "Untitled Project"}
            </h1>
          </div>
          <p className="text-on-surface-variant mt-1">Status: {status}</p>
        </div>
      </section>

      <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {[
          {
            label: "Design",
            path: `${projectId}/design`,
            icon: "hub",
            desc: "Run AI workflow",
            accent: "primary",
          },
          ...(state.deviceSelection
            ? [
                {
                  label: "Bill of Materials",
                  path: `${projectId}/bom`,
                  icon: "receipt_long",
                  desc: "View equipment list",
                  accent: "primary",
                },
              ]
            : []),
          {
            label: "Topology",
            path: `${projectId}/topology`,
            icon: "schema",
            desc: "Network diagrams",
            accent: "primary",
          },
          {
            label: "Deployment",
            path: `${projectId}/deployment`,
            icon: "rocket_launch",
            desc: "Push configs",
            accent: "tertiary",
          },
        ].map((card) => (
          <button
            key={card.label}
            onClick={() => navigate(`/project/${card.path}`)}
            className="bg-surface-container-low p-6 rounded-xl border border-outline-variant/15 hover:border-primary/30 transition-all text-left group"
          >
            <div className={`p-2 w-fit bg-${card.accent}/10 rounded-lg mb-4`}>
              <span className={`material-symbols-outlined text-${card.accent}`}>
                {card.icon}
              </span>
            </div>
            <div className="text-lg font-bold text-on-surface group-hover:text-primary transition-colors">
              {card.label}
            </div>
            <div className="text-sm text-on-surface-variant mt-1">
              {card.desc}
            </div>
          </button>
        ))}
      </section>

      <section className="pb-12">
        <div className="bg-surface-container-low rounded-xl border border-outline-variant/15 p-6">
          <h2 className="text-lg font-bold font-[family-name:var(--font-headline)] mb-4">
            Quick Actions
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:flex lg:flex-col gap-3">
            <button
              onClick={() => navigate(`/project/${projectId}/requirements`)}
              className="px-4 py-2 bg-primary text-on-primary font-bold rounded-lg hover:brightness-110 transition-all text-sm"
            >
              Edit Requirements
            </button>
            <button
              onClick={() => navigate(`/project/${projectId}/design`)}
              className="px-4 py-2 border border-outline-variant/30 text-on-surface font-medium rounded-lg hover:bg-surface-container-high transition-all text-sm"
            >
              {status === "In Progress" ? "Resume Design" : "Start Design"}
            </button>
            {state.deviceSelection && (
              <button
                onClick={() => navigate(`/project/${projectId}/bom`)}
                className="px-4 py-2 border border-outline-variant/30 text-on-surface font-medium rounded-lg hover:bg-surface-container-high transition-all text-sm"
              >
                View BOM
              </button>
            )}
            {state.diagramUrl && (
              <button
                onClick={() => navigate(`/project/${projectId}/topology`)}
                className="px-4 py-2 border border-outline-variant/30 text-on-surface font-medium rounded-lg hover:bg-surface-container-high transition-all text-sm"
              >
                View Topology
              </button>
            )}
            {state.workflowStatus === "complete" && (
              <button
                onClick={() => navigate(`/project/${projectId}/deployment`)}
                className="px-4 py-2 bg-gradient-to-r from-primary to-primary-container text-on-primary font-bold rounded-lg hover:brightness-110 transition-all text-sm"
              >
                Deploy
              </button>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}

export default function Dashboard() {
  const { projectId } = useParams();
  const { getProjectList } = useProject();

  if (projectId) {
    const meta = getProjectList().find((p) => p.id === projectId);
    return <ProjectDashboardView projectId={projectId} meta={meta} />;
  }

  return <ProjectListView />;
}
