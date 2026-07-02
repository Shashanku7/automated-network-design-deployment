/**
 * Requirements — Single-page simple form (replaces old Steps 1-3)
 *
 * DYNAMICALLY adapts based on solution type:
 *   - Campus: buildings, user, staff, sensitive areas
 *   - Data Center: server racks, compute, storage, redundancy
 *
 * ALL questions in plain English. Zero technical jargon.
 */
import { useState, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useProject } from "../context/ProjectContext";
// Workflow is triggered from ProposedDesign page via WebSocket

/* --- Options specific to Campus --- */
const campusSensitiveAreas = [
  { id: "finance", icon: "💰", label: "Finance Office" },
  { id: "exams", icon: "📝", label: "Examination Cell" },
  { id: "server", icon: "🖥️", label: "Server Room" },
  { id: "library", icon: "📚", label: "Library" },
  { id: "research", icon: "🔬", label: "Research Lab" },
  { id: "medical", icon: "🏥", label: "Medical Center" },
];
const campusRoles = [
  "Principal",
  "Exam Controller",
  "Finance Head",
  "Lab Instructor",
  "Hostel Warden",
];
const campusDevices = [
  { key: "laptops", icon: "💻", label: "Laptops & Desktops" },
  { key: "printers", icon: "🖨️", label: "Printers" },
  { key: "phones", icon: "📞", label: "Desk Phones" },
  { key: "cameras", icon: "📹", label: "Security Cameras" },
  { key: "wifi", icon: "📶", label: "Wi-Fi Access" },
];

/* --- Options specific to Data Center --- */
const dcSecurityZones = [
  { id: "production", icon: "🖥️", label: "Production Servers" },
  { id: "staging", icon: "🧪", label: "Staging / Test" },
  { id: "backup", icon: "💾", label: "Backup & Recovery" },
  { id: "management", icon: "🔧", label: "Management Network" },
  { id: "dmz", icon: "🌐", label: "Public-Facing Services" },
  { id: "storage", icon: "🗄️", label: "Storage Area" },
];
const dcEquipment = [
  { key: "servers", icon: "🖥️", label: "Rack Servers" },
  { key: "storage", icon: "🗄️", label: "Storage Systems" },
  { key: "ups", icon: "🔋", label: "UPS / Power" },
  { key: "cooling", icon: "❄️", label: "Cooling Systems" },
  { key: "monitoring", icon: "📊", label: "Monitoring Screens" },
];

export default function Requirements() {
  const navigate = useNavigate();
  const { projectId } = useParams();
  const { state, dispatch, loadProject } = useProject();
  const isCampus = state.solutionType !== "datacenter";
  const [form, setForm] = useState(state.requirements);
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState({});

  // Sync project state from URL params on mount
  useEffect(() => {
    if (projectId && state.projectId !== projectId) {
      loadProject(projectId);
    }
  }, [projectId, state.projectId, loadProject]);

  function set(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }
  function toggleDevice(device) {
    setForm((prev) => ({
      ...prev,
      devices: { ...prev.devices, [device]: !prev.devices[device] },
    }));
  }
  function toggleArea(areaId) {
    setForm((prev) => {
      const areas = prev.sensitiveAreas.includes(areaId)
        ? prev.sensitiveAreas.filter((a) => a !== areaId)
        : [...prev.sensitiveAreas, areaId];
      return { ...prev, sensitiveAreas: areas };
    });
  }
  function toggleRole(role) {
    setForm((prev) => {
      const roles = prev.specialRoles.includes(role)
        ? prev.specialRoles.filter((r) => r !== role)
        : [...prev.specialRoles, role];
      return { ...prev, specialRoles: roles };
    });
  }

  // Validate all required fields before submission
  function validate() {
    const errs = {};
    if (isCampus) {
      if (!form.buildingCount || Number(form.buildingCount) < 1) {
        errs.buildingCount = "Required";
      } else {
        form.buildings.forEach((b, bIdx) => {
          if (!b.name) errs[`b_${bIdx}_name`] = true;
          if (!b.departmentCount || Number(b.departmentCount) < 1)
            errs[`b_${bIdx}_dc`] = true;

          b.departments.forEach((d, dIdx) => {
            if (!d.department) errs[`b_${bIdx}_d_${dIdx}_dept`] = true;
            if (!d.students || Number(d.students) < 0)
              errs[`b_${bIdx}_d_${dIdx}_s`] = true;
            if (!d.admins || Number(d.admins) < 0)
              errs[`b_${bIdx}_d_${dIdx}_a`] = true;
            if (Number(d.admins) > Number(d.students || 0))
              errs[`b_${bIdx}_d_${dIdx}_a`] = true;
            if (!d.ap || Number(d.ap) < 0)
              errs[`b_${bIdx}_d_${dIdx}_ap`] = true;
            if (!d.switch || Number(d.switch) < 0)
              errs[`b_${bIdx}_d_${dIdx}_sw`] = true;
            if (!d.voip || Number(d.voip) < 0)
              errs[`b_${bIdx}_d_${dIdx}_v`] = true;
            if (
              (Number(d.ap) || 0) +
                (Number(d.switch) || 0) +
                (Number(d.voip) || 0) >
              Number(d.students || 0)
            )
              errs[`b_${bIdx}_d_${dIdx}_conn`] = true;
            if (!d.iptv || Number(d.iptv) < 0)
              errs[`b_${bIdx}_d_${dIdx}_i`] = true;
            if (!d.printers || Number(d.printers) < 0)
              errs[`b_${bIdx}_d_${dIdx}_pr`] = true;
          });
        });
      }
    } else {
      if (!form.dcRacks) errs.dcRacks = "Required";
      if (!form.dcServers) errs.dcServers = "Required";
    }
    return errs;
  }

  /* --- Campus Sync Logic --- */
  function updateBuildingCount(count) {
    const n = Math.max(0, Math.min(20, parseInt(count) || 0));
    setForm((prev) => {
      const buildings = [...prev.buildings];
      // Add new buildings if count increased
      while (buildings.length < n) {
        buildings.push({
          id: crypto.randomUUID(),
          name: "",
          departmentCount: "",
          departments: [],
        });
      }
      return {
        ...prev,
        buildingCount: count,
        buildings: buildings.slice(0, n),
      };
    });
  }

  function updateBuildingMeta(bIdx, field, val) {
    setForm((prev) => {
      const buildings = [...prev.buildings];
      buildings[bIdx][field] = val;

      // If department count changed, sync the departments array
      if (field === "departmentCount") {
        const fn = Math.max(0, Math.min(50, parseInt(val) || 0));
        const departments = [...buildings[bIdx].departments];
        while (departments.length < fn) {
          departments.push({
            name: "",
            department: "",
            floorNo: "",
            students: "",
            admins: "0",
            ap: "0",
            switch: "0",
            voip: "0",
            iptv: "0",
            printers: "0",
          });
        }
        buildings[bIdx].departments = departments.slice(0, fn);
        buildings[bIdx].departments.forEach((d, i) => {
          if (d.floorNo === "" || d.floorNo == null) d.floorNo = i;
        });
      }

      return { ...prev, buildings };
    });
  }

  function updateDept(bIdx, dIdx, field, val) {
    setForm((prev) => {
      const buildings = [...prev.buildings];
      buildings[bIdx].departments[dIdx][field] = val;
      return { ...prev, buildings };
    });
  }

  async function handleSubmit(e) {
    e.preventDefault();
    const errs = validate();
    setErrors(errs);
    if (Object.keys(errs).length > 0) {
      window.alert(
        "All primary input fields are compulsory! Please fill them before proceeding.",
      );
      window.scrollTo({ top: 0, behavior: "smooth" });
      return;
    }
    setSubmitting(true);
    dispatch({ type: "UPDATE_REQUIREMENTS", payload: form });
    dispatch({ type: "WORKFLOW_START" });
    // Persist state immediately — navigate triggers mount before dispatch effects flush
    try {
      const saved = JSON.parse(
        localStorage.getItem(`project_${projectId}`) || "{}",
      );
      saved.workflowStatus = "running";
      saved.solutionType = state.solutionType;
      saved.requirements = { ...form };
      saved.projectTitle = state.projectTitle;
      localStorage.setItem(`project_${projectId}`, JSON.stringify(saved));
    } catch {}
    navigate(`/project/${projectId}/design?fresh=1`);
  }

  return (
    <div className="h-full overflow-y-auto p-8 custom-scrollbar">
      <form onSubmit={handleSubmit} className="max-w-4xl mx-auto pb-24">
        {/* Back button to switch solution type */}
        <button
          type="button"
          onClick={() => navigate("/project/new")}
          className="flex items-center gap-2 text-on-surface-variant hover:text-primary transition-colors mb-6 group"
        >
          <span className="material-symbols-outlined text-lg group-hover:-translate-x-1 transition-transform">
            arrow_back
          </span>
          <span className="text-sm font-medium">Back to Solution Type</span>
        </button>

        <header className="mb-10">
          <div className="flex items-center gap-2 text-primary mb-2">
            <span className="material-symbols-outlined text-sm">edit_note</span>
            <span className="text-xs font-[family-name:var(--font-mono)] uppercase tracking-[0.2em]">
              {isCampus ? "Campus Setup" : "Data Center Setup"}
            </span>
          </div>
          <h1 className="text-3xl font-bold font-[family-name:var(--font-headline)] text-on-surface tracking-tight">
            {isCampus
              ? "Tell us about your campus"
              : "Tell us about your data center"}
          </h1>
          <p className="text-on-surface-variant mt-2 max-w-2xl">
            Answer a few simple questions. Our AI will design the perfect
            network for you.
          </p>

          {/* Validation error banner */}
          {Object.keys(errors).length > 0 && (
            <div className="mt-4 p-4 bg-error/10 border border-error/30 rounded-lg flex items-center gap-3">
              <span className="material-symbols-outlined text-error">
                error
              </span>
              <span className="text-sm text-error font-medium">
                Please fill in all required fields before proceeding.
              </span>
            </div>
          )}
        </header>

        {/* ========== CAMPUS-SPECIFIC SECTIONS ========== */}
        {isCampus && (
          <>
            <Section title="Campus Overview" icon="apartment">
              <div className="max-w-xs">
                <NumberInput
                  label="How many buildings in total?"
                  value={form.buildingCount}
                  onChange={updateBuildingCount}
                  placeholder="e.g. 3"
                  error={errors.buildingCount}
                  required
                />
              </div>
            </Section>

            {Number(form.buildingCount) > 0 && (
              <Section title="Building Details" icon="edit_square">
                <p className="text-on-surface-variant text-sm mb-6">
                  Tell us the name and number of departments for each building.
                </p>
                <div className="space-y-4">
                  {form.buildings.map((b, i) => (
                    <div
                      key={b.id}
                      className="grid grid-cols-1 md:grid-cols-3 gap-4 bg-surface-container-low p-4 rounded-xl border border-outline-variant/20 items-end"
                    >
                      <div className="md:col-span-2 space-y-2">
                        <label className="text-xs font-bold text-primary uppercase">
                          Building {i + 1} Name
                        </label>
                        <input
                          type="text"
                          placeholder="e.g. Main Block, Library, Hostel"
                          value={b.name}
                          onChange={(e) =>
                            updateBuildingMeta(i, "name", e.target.value)
                          }
                          className={`w-full bg-surface-container-highest border rounded-lg px-4 py-2 text-on-surface focus:ring-1 focus:ring-primary outline-none transition-all ${
                            b.name?.trim()
                              ? "border-tertiary/60 ring-1 ring-tertiary/20"
                              : "border-error/60 ring-1 ring-error/20"
                          }`}
                        />
                      </div>
                      <div className="space-y-2">
                        <label className="text-xs font-bold text-primary uppercase">
                          Number of Departments
                        </label>
                        <input
                          type="number"
                          min="1"
                          placeholder="e.g. 3"
                          value={b.departmentCount}
                          onChange={(e) =>
                            updateBuildingMeta(
                              i,
                              "departmentCount",
                              e.target.value,
                            )
                          }
                          className={`w-full bg-surface-container-highest border rounded-lg px-4 py-2 text-on-surface focus:ring-1 focus:ring-primary outline-none transition-all ${
                            b.departmentCount && Number(b.departmentCount) > 0
                              ? "border-tertiary/60 ring-1 ring-tertiary/20"
                              : "border-error/60 ring-1 ring-error/20"
                          }`}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </Section>
            )}

            {form.buildings.some(
              (b) => b.name && Number(b.departmentCount) > 0,
            ) && (
              <Section title="Who will use the network?" icon="group">
                <div className="mb-6 p-4 bg-primary/10 border border-primary/30 rounded-lg">
                  <p className="text-sm text-on-surface font-medium mb-2">
                    Enter the user and device counts for each department below.
                  </p>
                  <ul className="text-sm text-on-surface-variant space-y-1 list-disc list-inside">
                    <li>
                      <strong className="text-primary">Users*</strong> — total
                      users in this department (mandatory)
                    </li>
                    <li>
                      <strong className="text-primary">Admin</strong> — admins
                      among the Users (subset, don't double-count)
                    </li>
                    <li>
                      <strong className="text-primary">AP (Wi-Fi)</strong> —
                      users connecting via Wi-Fi
                    </li>
                    <li>
                      <strong className="text-primary">
                        Switch (Ethernet)
                      </strong>{" "}
                      — users with direct wired switch connection
                    </li>
                    <li>
                      <strong className="text-primary">VoIP (Telephone)</strong>{" "}
                      — users connecting via IP phones
                    </li>
                    <li>
                      <strong className="text-primary">IPTV</strong> —
                      standalone IPTV devices (right table, not counted as
                      users)
                    </li>
                    <li>
                      <strong className="text-primary">Printers</strong> —
                      standalone network printers (right table, not counted as
                      users)
                    </li>
                  </ul>
                  <p className="text-xs text-on-surface-variant mt-3 italic">
                    Note: AP (Wi-Fi) + Switch (Ethernet) + VoIP (Telephone) must
                    be equal to or less than Users. Any uncovered users are
                    assumed to connect via Wi-Fi (AP) automatically. Admin is a
                    subset of Users — do not double-count.
                  </p>
                </div>

                <div className="space-y-12">
                  {form.buildings
                    .filter((b) => b.name && Number(b.departmentCount) > 0)
                    .map((building) => {
                      const bIdx = form.buildings.findIndex(
                        (b) => b.id === building.id,
                      );
                      return (
                        <div key={building.id} className="space-y-4">
                          <div className="flex items-center gap-2 text-primary border-l-4 border-primary pl-4 py-1">
                            <span className="material-symbols-outlined">
                              domain
                            </span>
                            <h3 className="font-bold text-lg">
                              {building.name}
                            </h3>
                            <span className="text-xs text-on-surface-variant bg-surface-container px-2 py-0.5 rounded ml-2">
                              {building.departmentCount} Departments
                            </span>
                          </div>

                          <div className="flex flex-col gap-6">
                            {/* Table 1: User/device counts */}
                            <div className="overflow-x-auto border border-outline-variant/10 rounded-xl bg-surface-container-low shadow-sm">
                              <table
                                className="w-full text-sm"
                                style={{ tableLayout: "fixed" }}
                              >
                                <colgroup>
                                  <col style={{ width: "30%" }} />
                                  <col style={{ width: "14%" }} />
                                  <col style={{ width: "14%" }} />
                                  <col style={{ width: "14%" }} />
                                  <col style={{ width: "14%" }} />
                                  <col style={{ width: "14%" }} />
                                </colgroup>
                                <thead className="bg-surface-container text-on-surface-variant">
                                  <tr>
                                    <th className="px-4 py-3 text-left font-medium">
                                      Department Name*
                                    </th>
                                    <th className="px-4 py-3 text-left font-medium">
                                      Floor No.
                                    </th>
                                    <th className="px-4 py-3 text-left font-medium">
                                      Users*
                                    </th>
                                    <th className="px-4 py-3 text-left font-medium">
                                      Admin
                                    </th>
                                    <th className="px-4 py-3 text-left font-medium">
                                      AP (Wi-Fi)
                                    </th>
                                    <th className="px-4 py-3 text-left font-medium">
                                      Switch (Ethernet)
                                    </th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y divide-outline-variant/10">
                                  {building.departments.map((dept, dIdx) => {
                                    const rowError =
                                      errors[`b_${bIdx}_d_${dIdx}_dept`] ||
                                      errors[`b_${bIdx}_d_${dIdx}_s`] ||
                                      errors[`b_${bIdx}_d_${dIdx}_a`] ||
                                      errors[`b_${bIdx}_d_${dIdx}_ap`] ||
                                      errors[`b_${bIdx}_d_${dIdx}_sw`] ||
                                      errors[`b_${bIdx}_d_${dIdx}_conn`] ||
                                      errors[`b_${bIdx}_d_${dIdx}_i`] ||
                                      errors[`b_${bIdx}_d_${dIdx}_pr`];
                                    return (
                                      <tr
                                        key={dIdx}
                                        className={`transition-colors ${rowError ? "bg-error/5" : ""}`}
                                      >
                                        <td className="px-4 py-2">
                                          <input
                                            type="text"
                                            placeholder="e.g. CSE, Library, Admin"
                                            value={dept.department}
                                            onChange={(e) =>
                                              updateDept(
                                                bIdx,
                                                dIdx,
                                                "department",
                                                e.target.value,
                                              )
                                            }
                                            className={`w-full bg-transparent border-b px-1 py-1 outline-none transition-all ${
                                              dept.department?.trim()
                                                ? "border-tertiary/60"
                                                : "border-error/60"
                                            }`}
                                          />
                                        </td>
                                        <td className="px-4 py-2">
                                          <input
                                            type="number"
                                            min="0"
                                            placeholder="0"
                                            value={dept.floorNo}
                                            onChange={(e) =>
                                              updateDept(
                                                bIdx,
                                                dIdx,
                                                "floorNo",
                                                e.target.value,
                                              )
                                            }
                                            className="w-full bg-surface-container-highest rounded-md px-3 py-2 border border-outline-variant/20 focus:border-primary text-center transition-all"
                                          />
                                        </td>
                                        <td className="px-4 py-2">
                                          <input
                                            type="number"
                                            min="0"
                                            placeholder="0"
                                            value={dept.students}
                                            onChange={(e) =>
                                              updateDept(
                                                bIdx,
                                                dIdx,
                                                "students",
                                                e.target.value,
                                              )
                                            }
                                            className={`w-full bg-surface-container-highest rounded-md px-3 py-2 border transition-all ${
                                              dept.students !== ""
                                                ? "border-tertiary/60 ring-1 ring-tertiary/20"
                                                : "border-error/60 ring-1 ring-error/20"
                                            }`}
                                          />
                                        </td>
                                        <td className="px-4 py-2">
                                          <input
                                            type="number"
                                            min="0"
                                            placeholder="0"
                                            value={dept.admins}
                                            onChange={(e) =>
                                              updateDept(
                                                bIdx,
                                                dIdx,
                                                "admins",
                                                e.target.value,
                                              )
                                            }
                                            className={`w-full bg-surface-container-highest rounded-md px-3 py-2 border transition-all ${
                                              rowError
                                                ? "border-error/60 ring-1 ring-error/20"
                                                : dept.admins !== "" &&
                                                    dept.admins !== "0"
                                                  ? "border-tertiary/60 ring-1 ring-tertiary/20"
                                                  : "border-outline-variant/20"
                                            }`}
                                          />
                                        </td>
                                        <td className="px-4 py-2">
                                          <input
                                            type="number"
                                            min="0"
                                            placeholder="0"
                                            value={dept.ap}
                                            onChange={(e) =>
                                              updateDept(
                                                bIdx,
                                                dIdx,
                                                "ap",
                                                e.target.value,
                                              )
                                            }
                                            className={`w-full bg-surface-container-highest rounded-md px-3 py-2 border transition-all ${
                                              rowError
                                                ? "border-error/60 ring-1 ring-error/20"
                                                : dept.ap !== "" &&
                                                    dept.ap !== "0"
                                                  ? "border-tertiary/60 ring-1 ring-tertiary/20"
                                                  : "border-outline-variant/20"
                                            }`}
                                          />
                                        </td>
                                        <td className="px-4 py-2">
                                          <input
                                            type="number"
                                            min="0"
                                            placeholder="0"
                                            value={dept.switch}
                                            onChange={(e) =>
                                              updateDept(
                                                bIdx,
                                                dIdx,
                                                "switch",
                                                e.target.value,
                                              )
                                            }
                                            className={`w-full bg-surface-container-highest rounded-md px-3 py-2 border transition-all ${
                                              rowError
                                                ? "border-error/60 ring-1 ring-error/20"
                                                : dept.switch !== "" &&
                                                    dept.switch !== "0"
                                                  ? "border-tertiary/60 ring-1 ring-tertiary/20"
                                                  : "border-outline-variant/20"
                                            }`}
                                          />
                                        </td>
                                      </tr>
                                    );
                                  })}
                                </tbody>
                                <tfoot className="bg-surface-container/50">
                                  <tr className="font-bold text-primary">
                                    <td className="px-4 py-3 text-xs uppercase tracking-wider text-on-surface-variant"></td>
                                    <td className="px-4 py-3 text-xs uppercase tracking-wider text-on-surface-variant">
                                      Total
                                    </td>
                                    <td className="px-4 py-3">
                                      {building.departments.reduce(
                                        (s, d) => s + (Number(d.students) || 0),
                                        0,
                                      )}
                                    </td>
                                    <td className="px-4 py-3">
                                      {building.departments.reduce(
                                        (s, d) => s + (Number(d.admins) || 0),
                                        0,
                                      )}
                                    </td>
                                    <td className="px-4 py-3">
                                      {building.departments.reduce(
                                        (s, d) => s + (Number(d.ap) || 0),
                                        0,
                                      )}
                                    </td>
                                    <td className="px-4 py-3">
                                      {building.departments.reduce(
                                        (s, d) => s + (Number(d.switch) || 0),
                                        0,
                                      )}
                                    </td>
                                  </tr>
                                </tfoot>
                              </table>
                            </div>

                            {/* Table 2: End devices */}
                            <div className="overflow-x-auto border border-outline-variant/10 rounded-xl bg-surface-container-low shadow-sm">
                              <table
                                className="w-full text-sm"
                                style={{ tableLayout: "fixed" }}
                              >
                                <colgroup>
                                  <col style={{ width: "25%" }} />
                                  <col style={{ width: "25%" }} />
                                  <col style={{ width: "25%" }} />
                                  <col style={{ width: "25%" }} />
                                </colgroup>
                                <thead className="bg-surface-container text-on-surface-variant">
                                  <tr>
                                    <th className="px-4 py-3 text-left font-medium">
                                      Department
                                    </th>
                                    <th className="px-4 py-3 text-left font-medium">
                                      VoIP (Telephone)
                                    </th>
                                    <th className="px-4 py-3 text-left font-medium">
                                      IPTV
                                    </th>
                                    <th className="px-4 py-3 text-left font-medium">
                                      Printers
                                    </th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y divide-outline-variant/10">
                                  {building.departments.map((dept, dIdx) => {
                                    const rowError =
                                      errors[`b_${bIdx}_d_${dIdx}_dept`] ||
                                      errors[`b_${bIdx}_d_${dIdx}_v`] ||
                                      errors[`b_${bIdx}_d_${dIdx}_i`] ||
                                      errors[`b_${bIdx}_d_${dIdx}_pr`];
                                    return (
                                      <tr
                                        key={dIdx}
                                        className={`transition-colors ${rowError ? "bg-error/5" : ""}`}
                                      >
                                        <td className="px-4 py-2">
                                          <span className="text-sm text-on-surface-variant">
                                            {dept.department ||
                                              `Dept ${dIdx + 1}`}
                                          </span>
                                        </td>
                                        <td className="px-4 py-2">
                                          <input
                                            type="number"
                                            min="0"
                                            placeholder="0"
                                            value={dept.voip}
                                            onChange={(e) =>
                                              updateDept(
                                                bIdx,
                                                dIdx,
                                                "voip",
                                                e.target.value,
                                              )
                                            }
                                            className={`w-full max-w-24 bg-surface-container-highest rounded-md px-3 py-2 border transition-all ${
                                              rowError
                                                ? "border-error/60 ring-1 ring-error/20"
                                                : dept.voip !== "" &&
                                                    dept.voip !== "0"
                                                  ? "border-tertiary/60 ring-1 ring-tertiary/20"
                                                  : "border-outline-variant/20"
                                            }`}
                                          />
                                        </td>
                                        <td className="px-4 py-2">
                                          <input
                                            type="number"
                                            min="0"
                                            placeholder="0"
                                            value={dept.iptv}
                                            onChange={(e) =>
                                              updateDept(
                                                bIdx,
                                                dIdx,
                                                "iptv",
                                                e.target.value,
                                              )
                                            }
                                            className={`w-full max-w-24 bg-surface-container-highest rounded-md px-3 py-2 border transition-all ${
                                              rowError
                                                ? "border-error/60 ring-1 ring-error/20"
                                                : dept.iptv !== "" &&
                                                    dept.iptv !== "0"
                                                  ? "border-tertiary/60 ring-1 ring-tertiary/20"
                                                  : "border-outline-variant/20"
                                            }`}
                                          />
                                        </td>
                                        <td className="px-4 py-2">
                                          <input
                                            type="number"
                                            min="0"
                                            placeholder="0"
                                            value={dept.printers}
                                            onChange={(e) =>
                                              updateDept(
                                                bIdx,
                                                dIdx,
                                                "printers",
                                                e.target.value,
                                              )
                                            }
                                            className={`w-full max-w-24 bg-surface-container-highest rounded-md px-3 py-2 border transition-all ${
                                              rowError
                                                ? "border-error/60 ring-1 ring-error/20"
                                                : dept.printers !== "" &&
                                                    dept.printers !== "0"
                                                  ? "border-tertiary/60 ring-1 ring-tertiary/20"
                                                  : "border-outline-variant/20"
                                            }`}
                                          />
                                        </td>
                                      </tr>
                                    );
                                  })}
                                </tbody>
                                <tfoot className="bg-surface-container/50">
                                  <tr className="font-bold text-primary">
                                    <td className="px-4 py-3 text-xs uppercase tracking-wider text-on-surface-variant">
                                      Total
                                    </td>
                                    <td className="px-4 py-3">
                                      {building.departments.reduce(
                                        (s, d) => s + (Number(d.voip) || 0),
                                        0,
                                      )}
                                    </td>
                                    <td className="px-4 py-3">
                                      {building.departments.reduce(
                                        (s, d) => s + (Number(d.iptv) || 0),
                                        0,
                                      )}
                                    </td>
                                    <td className="px-4 py-3">
                                      {building.departments.reduce(
                                        (s, d) => s + (Number(d.printers) || 0),
                                        0,
                                      )}
                                    </td>
                                  </tr>
                                </tfoot>
                              </table>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                </div>
              </Section>
            )}
          </>
        )}

        {/* ========== DATA CENTER-SPECIFIC SECTIONS ========== */}
        {!isCampus && (
          <>
            <Section title="About Your Facility" icon="warehouse">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <NumberInput
                  label="How many server racks?"
                  value={form.dcRacks}
                  onChange={(v) => set("dcRacks", v)}
                  placeholder="e.g. 10"
                  error={errors.dcRacks}
                  required
                />
                <NumberInput
                  label="How many servers (approx)?"
                  value={form.dcServers}
                  onChange={(v) => set("dcServers", v)}
                  placeholder="e.g. 50"
                  error={errors.dcServers}
                  required
                />
              </div>
            </Section>

            <Section title="What's it used for?" icon="apps">
              <p className="text-on-surface-variant text-sm mb-4">
                Select all that apply.
              </p>
              <div className="flex flex-wrap gap-2">
                {[
                  "Web Hosting",
                  "Database Storage",
                  "Application Servers",
                  "File Storage",
                  "Email Services",
                  "Video Streaming",
                  "AI / Machine Learning",
                  "Backup & Disaster Recovery",
                ].map((use) => (
                  <ChipToggle
                    key={use}
                    label={use}
                    active={form.specialRoles.includes(use)}
                    onClick={() => toggleRole(use)}
                  />
                ))}
              </div>
            </Section>

            <Section title="What equipment do you have?" icon="memory">
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                {dcEquipment.map((d) => (
                  <DeviceToggle
                    key={d.key}
                    {...d}
                    active={form.devices[d.key]}
                    onClick={() => toggleDevice(d.key)}
                  />
                ))}
              </div>
            </Section>

            <Section title="Security zones" icon="shield">
              <p className="text-on-surface-variant text-sm mb-4">
                Select which zones need separate network segments.
              </p>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                {dcSecurityZones.map((area) => (
                  <AreaToggle
                    key={area.id}
                    {...area}
                    active={form.sensitiveAreas.includes(area.id)}
                    onClick={() => toggleArea(area.id)}
                  />
                ))}
              </div>
            </Section>
          </>
        )}

        {/* ========== SHARED SECTIONS (both types) ========== */}

        <Section title="How important is network uptime?" icon="speed">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[
              {
                val: "standard",
                label: "Standard",
                desc: "Occasional brief outages are acceptable",
                color: "tertiary",
              },
              {
                val: "important",
                label: "Important",
                desc: "Minimal downtime, critical for daily operations",
                color: "primary",
              },
              {
                val: "critical",
                label: "Mission Critical",
                desc: "24/7 availability, no downtime allowed",
                color: "error",
              },
            ].map((opt) => (
              <button
                type="button"
                key={opt.val}
                onClick={() => set("uptimeLevel", opt.val)}
                className={`p-5 rounded-xl border text-left transition-all ${
                  form.uptimeLevel === opt.val
                    ? `bg-${opt.color}/10 border-${opt.color}/40`
                    : "bg-surface-container-low border-outline-variant/15 hover:border-outline-variant/30"
                }`}
              >
                <div
                  className={`text-sm font-bold ${form.uptimeLevel === opt.val ? `text-${opt.color}` : "text-on-surface"}`}
                >
                  {opt.label}
                </div>
                <div className="text-xs text-on-surface-variant mt-1">
                  {opt.desc}
                </div>
              </button>
            ))}
          </div>
        </Section>

        <Section title="Future plans" icon="trending_up">
          <div className="mb-4 p-4 bg-primary/10 border border-primary/30 rounded-lg flex items-start gap-3">
            <span className="material-symbols-outlined text-primary mt-0.5">
              info
            </span>
            <p className="text-sm text-on-surface font-medium">
              All designs include a{" "}
              <strong className="text-primary">
                1.2x (20% growth margin — applied by default)
              </strong>{" "}
              on top of your current user/device counts — automatically applied
              to future-proof the network.
            </p>
          </div>
          <div className="max-w-xs">
            <NumberInput
              label={
                isCampus
                  ? "Do you expect your campus to grow? (Expected additional users/people)"
                  : "Do you expect to add more capacity? (Expected additional server racks)"
              }
              value={form.growthAmount}
              onChange={(v) => {
                set("growthAmount", v);
                set("expectGrowth", Number(v) > 0);
              }}
              placeholder={isCampus ? "e.g. 150" : "e.g. 5"}
            />
          </div>
        </Section>

        <Section
          title="Anything else (optional: mention the split of users using AP and ethernet)?"
          icon="chat"
        >
          <textarea
            value={form.additionalNotes}
            onChange={(e) => set("additionalNotes", e.target.value)}
            rows={4}
            className="w-full bg-surface-container-low border border-outline-variant/30 rounded-lg px-4 py-3 text-on-surface placeholder:text-outline/50 focus:ring-1 focus:ring-primary resize-none"
            placeholder={
              isCampus
                ? "Describe anything else. E.g. 'We have a library with 50 computers, a hostel block, and want CCTV in parking areas.'"
                : "Describe anything else. E.g. 'We need 10Gbps uplinks between racks and a separate management network.'"
            }
          />
        </Section>

        {/* Submit */}
        <div className="fixed bottom-0 left-0 right-0 bg-surface/80 backdrop-blur-md border-t border-outline-variant/15 p-4 flex justify-end z-30">
          <button
            type="submit"
            disabled={submitting}
            className="px-8 py-3 bg-gradient-to-r from-primary to-primary-container text-on-primary font-bold rounded-lg shadow-lg shadow-primary/20 hover:brightness-110 active:scale-[0.98] transition-all flex items-center gap-3 disabled:opacity-50 mr-4"
          >
            <span className="material-symbols-outlined">auto_awesome</span>
            {submitting ? "Generating..." : "Generate My Network Design"}
          </button>
        </div>
      </form>
    </div>
  );
}

/* --- Reusable Sub-Components --- */

function Section({ title, icon, children }) {
  return (
    <section className="mb-10">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center">
          <span className="material-symbols-outlined text-primary text-lg">
            {icon}
          </span>
        </div>
        <h2 className="text-lg font-bold font-[family-name:var(--font-headline)] text-on-surface">
          {title}
        </h2>
      </div>
      {children}
    </section>
  );
}

function NumberInput({ label, value, onChange, placeholder, error, required }) {
  const hasValue = value !== "" && value !== undefined && value !== null;
  return (
    <div className="space-y-2">
      <label className="text-sm font-medium text-on-surface-variant">
        {label}
        {required && <span className="text-error ml-1">*</span>}
      </label>
      <input
        type="number"
        min="0"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={`w-full bg-surface-container-low border rounded-lg px-4 py-3 text-on-surface placeholder:text-outline/50 focus:ring-1 focus:ring-primary focus:border-primary transition-colors ${
          required && !hasValue
            ? "border-error/60 ring-1 ring-error/20"
            : required && hasValue
              ? "border-tertiary/60 ring-1 ring-tertiary/20"
              : error
                ? "border-error/60 ring-1 ring-error/20"
                : "border-outline-variant/30"
        }`}
      />
      {error && (
        <span className="text-[10px] text-error font-medium uppercase tracking-wider">
          {error}
        </span>
      )}
    </div>
  );
}

function ChipToggle({ label, active, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${
        active
          ? "bg-primary/20 text-primary border border-primary/40"
          : "bg-surface-container-high text-on-surface-variant border border-transparent hover:border-outline-variant/30"
      }`}
    >
      {label}
    </button>
  );
}

function DeviceToggle({ icon, label, active, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex flex-col items-center gap-2 p-4 rounded-xl border transition-all text-center ${
        active
          ? "bg-primary/10 border-primary/40 text-primary"
          : "bg-surface-container-low border-outline-variant/15 text-on-surface-variant hover:border-outline-variant/30"
      }`}
    >
      <span className="text-2xl">{icon}</span>
      <span className="text-xs font-medium">{label}</span>
    </button>
  );
}

function AreaToggle({ icon, label, active, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex items-center gap-3 p-4 rounded-xl border transition-all text-left ${
        active
          ? "bg-tertiary/10 border-tertiary/40"
          : "bg-surface-container-low border-outline-variant/15 hover:border-outline-variant/30"
      }`}
    >
      <span className="text-2xl">{icon}</span>
      <span className="text-sm font-medium text-on-surface">{label}</span>
    </button>
  );
}
