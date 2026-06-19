import { useNavigate } from "react-router-dom";
import { useProject } from "../context/ProjectContext";

const solutions = [
  {
    id: "campus",
    icon: "school",
    title: "Campus Network",
    subtitle: "Schools, colleges & multi-building campuses",
    desc: "Connect classrooms, offices, hostels, and labs across multiple buildings with reliable networking and Wi-Fi.",
    tags: [
      "Multi-building",
      "Student Wi-Fi",
      "Camera support",
      "Guest network",
    ],
  },
  {
    id: "datacenter",
    icon: "dns",
    title: "Data Center",
    subtitle: "High-performance server infrastructure",
    desc: "Set up a robust data center with high-speed switching, redundancy, and server connectivity.",
    tags: [
      "High-speed backbone",
      "Server racks",
      "Redundancy",
      "Storage network",
    ],
  },
];

export default function SolutionType() {
  const navigate = useNavigate();
  const { dispatch, createProject } = useProject();

  function handleSelect(type) {
    const title = `New ${type === "campus" ? "Campus Network" : "Data Center"} Design`;
    const projectId = createProject(title);
    dispatch({ type: "SET_SOLUTION_TYPE", payload: type });
    navigate(`/project/${projectId}/requirements`);
  }

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <header className="text-center mb-12 mt-8">
        <div className="flex items-center justify-center gap-2 text-primary mb-3">
          <span className="material-symbols-outlined text-sm">
            auto_awesome
          </span>
          <span className="text-xs font-[family-name:var(--font-mono)] uppercase tracking-[0.2em]">
            New Design Wizard
          </span>
        </div>
        <h1 className="text-4xl font-bold font-[family-name:var(--font-headline)] text-on-surface tracking-tight">
          What would you like to build?
        </h1>
        <p className="text-on-surface-variant mt-3 max-w-xl mx-auto">
          Select the type of network you need. We'll ask a few simple questions,
          then design the perfect solution.
        </p>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {solutions.map((sol) => (
          <button
            key={sol.id}
            onClick={() => handleSelect(sol.id)}
            className="group text-left bg-surface-container-low rounded-2xl border border-outline-variant/15 p-8 hover:border-primary/40 hover:shadow-[0_0_40px_rgba(60,215,255,0.08)] transition-all duration-300 relative overflow-hidden"
          >
            <div className="absolute -top-16 -right-16 w-40 h-40 bg-primary/5 rounded-full blur-3xl group-hover:bg-primary/15 transition-colors duration-500" />
            <div className="w-16 h-16 rounded-xl bg-primary/10 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
              <span className="material-symbols-outlined text-primary text-3xl">
                {sol.icon}
              </span>
            </div>
            <h2 className="text-2xl font-bold font-[family-name:var(--font-headline)] text-on-surface group-hover:text-primary transition-colors">
              {sol.title}
            </h2>
            <p className="text-on-surface-variant text-sm mt-1">
              {sol.subtitle}
            </p>
            <p className="text-on-surface/70 text-sm mt-4 leading-relaxed">
              {sol.desc}
            </p>
            <div className="flex flex-wrap gap-2 mt-6">
              {sol.tags.map((t) => (
                <span
                  key={t}
                  className="text-xs bg-surface-container-high text-on-surface-variant px-3 py-1 rounded-full"
                >
                  {t}
                </span>
              ))}
            </div>
            <div className="flex items-center gap-2 mt-8 text-outline group-hover:text-primary transition-colors">
              <span className="text-sm font-medium">Get Started</span>
              <span className="material-symbols-outlined group-hover:translate-x-1 transition-transform">
                arrow_forward
              </span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
