import { useMemo } from "react";
import { NavLink, useNavigate, useParams } from "react-router-dom";
import { useProject } from "../context/ProjectContext";
import { useSidebar } from "../context/SidebarContext";

const BASE_NAV = [
  { icon: "dashboard", label: "Dashboard" },
  { icon: "list_alt", label: "Requirements" },
  { icon: "hub", label: "Design" },
  { icon: "receipt_long", label: "BOM" },
  { icon: "account_tree", label: "Topology" },
  { icon: "rocket_launch", label: "Deployment" },
];

export default function Sidebar() {
  const navigate = useNavigate();
  const { projectId } = useParams();
  const { state } = useProject();
  const { open, close } = useSidebar();
  const base = projectId ? `/project/${projectId}` : "";
  const isInProject = !!projectId;

  const showBom = !!state.deviceSelection;
  const showTopology = !!state.reactCode;
  const navItems = useMemo(
    () => BASE_NAV.filter(
      (item) => (item.label !== "BOM" || showBom) && (item.label !== "Topology" || showTopology),
    ),
    [showBom, showTopology],
  );

  function handleNewDesign() {
    navigate("/project/new");
  }

  function navPath(label) {
    if (!isInProject) return "/";
    const map = {
      Dashboard: base,
      Requirements: `${base}/requirements`,
      Design: `${base}/design`,
      BOM: `${base}/bom`,
      Topology: `${base}/interactive-topology`,
      Deployment: `${base}/deployment`,
    };
    return map[label] || "/";
  }

  return (
    <>
      {/* Overlay backdrop for mobile */}
      {open && (
        <div
          className="fixed inset-0 top-14 z-30 bg-black/50"
          onClick={close}
        />
      )}

      <aside
        className={`flex flex-col fixed left-0 top-14 h-[calc(100vh-3.5rem)] z-40 w-64 border-r border-outline-variant/15 bg-surface-dim font-body text-sm font-medium transition-transform duration-300 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="p-6 flex flex-col h-full">
          <nav className="flex flex-col gap-1">
            {navItems.map((item) => (
              <NavLink
                key={item.label}
                to={navPath(item.label)}
                end={item.label === "Dashboard" || !isInProject}
                onClick={(e) => {
                  if (!isInProject && item.label !== "Dashboard") {
                    e.preventDefault();
                    return;
                  }
                  close();
                }}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-4 py-3 rounded-md transition-all ${
                    !isInProject && item.label !== "Dashboard"
                      ? "text-outline/30 cursor-not-allowed"
                      : isActive
                        ? "text-primary border-r-2 border-primary bg-gradient-to-r from-primary/10 to-transparent font-bold"
                        : "text-on-surface/60 hover:text-on-surface hover:bg-surface"
                  }`
                }
              >
                <span className="material-symbols-outlined">{item.icon}</span>
                {item.label}
              </NavLink>
            ))}
          </nav>

        <div className="mt-auto space-y-4">
          <button
            onClick={handleNewDesign}
            className="w-full bg-gradient-to-br from-primary to-primary-container text-on-primary font-bold py-2.5 rounded-md flex items-center justify-center gap-2 hover:brightness-110 transition-all active:scale-[0.98]"
          >
            <span className="material-symbols-outlined text-lg">add</span>
            New Design
          </button>

          <button
            onClick={() =>
              window.open(
                "https://www.arubanetworks.com/techdocs/central/latest/content/home.htm",
                "_blank",
              )
            }
            className="w-full flex items-center gap-3 px-3 py-2 text-on-surface/60 hover:text-on-surface transition-all text-left"
          >
            <span className="material-symbols-outlined text-xl">
              description
            </span>
            Documentation
          </button>
          <button
            onClick={() =>
              window.open("https://networkingsupport.hpe.com", "_blank")
            }
            className="w-full flex items-center gap-3 px-3 py-2 text-on-surface/60 hover:text-on-surface transition-all text-left"
          >
            <span className="material-symbols-outlined text-xl">help</span>
            Support
          </button>
        </div>
        </div>
      </aside>
    </>
  );
}
