/**
 * Requirements — Single-page simple form (replaces old Steps 1-3)
 * 
 * DYNAMICALLY adapts based on solution type:
 *   - Campus: buildings, students, staff, sensitive areas
 *   - Data Center: server racks, compute, storage, redundancy
 * 
 * ALL questions in plain English. Zero technical jargon.
 */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useProject } from '../context/ProjectContext';
import { submitRequirements } from '../services/api';

/* --- Options specific to Campus --- */
const campusSensitiveAreas = [
  { id: 'finance', icon: '💰', label: 'Finance Office' },
  { id: 'exams', icon: '📝', label: 'Examination Cell' },
  { id: 'server', icon: '🖥️', label: 'Server Room' },
  { id: 'library', icon: '📚', label: 'Library' },
  { id: 'research', icon: '🔬', label: 'Research Lab' },
  { id: 'medical', icon: '🏥', label: 'Medical Center' },
];
const campusRoles = ['Principal', 'Exam Controller', 'Finance Head', 'Lab Instructor', 'Hostel Warden'];
const campusDevices = [
  { key: 'laptops', icon: '💻', label: 'Laptops & Desktops' },
  { key: 'printers', icon: '🖨️', label: 'Printers' },
  { key: 'phones', icon: '📞', label: 'Desk Phones' },
  { key: 'cameras', icon: '📹', label: 'Security Cameras' },
  { key: 'wifi', icon: '📶', label: 'Wi-Fi Access' },
];

/* --- Options specific to Data Center --- */
const dcSecurityZones = [
  { id: 'production', icon: '🖥️', label: 'Production Servers' },
  { id: 'staging', icon: '🧪', label: 'Staging / Test' },
  { id: 'backup', icon: '💾', label: 'Backup & Recovery' },
  { id: 'management', icon: '🔧', label: 'Management Network' },
  { id: 'dmz', icon: '🌐', label: 'Public-Facing Services' },
  { id: 'storage', icon: '🗄️', label: 'Storage Area' },
];
const dcEquipment = [
  { key: 'servers', icon: '🖥️', label: 'Rack Servers' },
  { key: 'storage', icon: '🗄️', label: 'Storage Systems' },
  { key: 'ups', icon: '🔋', label: 'UPS / Power' },
  { key: 'cooling', icon: '❄️', label: 'Cooling Systems' },
  { key: 'monitoring', icon: '📊', label: 'Monitoring Screens' },
];

export default function Requirements() {
  const navigate = useNavigate();
  const { state, dispatch } = useProject();
  const isCampus = state.solutionType !== 'datacenter';
  const [form, setForm] = useState(state.requirements);
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState({});

  function set(field, value) {
    setForm(prev => ({ ...prev, [field]: value }));
  }
  function toggleDevice(device) {
    setForm(prev => ({ ...prev, devices: { ...prev.devices, [device]: !prev.devices[device] } }));
  }
  function toggleArea(areaId) {
    setForm(prev => {
      const areas = prev.sensitiveAreas.includes(areaId) ? prev.sensitiveAreas.filter(a => a !== areaId) : [...prev.sensitiveAreas, areaId];
      return { ...prev, sensitiveAreas: areas };
    });
  }
  function toggleRole(role) {
    setForm(prev => {
      const roles = prev.specialRoles.includes(role) ? prev.specialRoles.filter(r => r !== role) : [...prev.specialRoles, role];
      return { ...prev, specialRoles: roles };
    });
  }

  // Validate all required fields before submission
  function validate() {
    const errs = {};
    if (isCampus) {
      if (!form.buildingCount || Number(form.buildingCount) < 1) {
        errs.buildingCount = 'Required';
      } else {
        form.buildings.forEach((b, bIdx) => {
          if (!b.name) errs[`b_${bIdx}_name`] = true;
          if (!b.floorCount || Number(b.floorCount) < 1) errs[`b_${bIdx}_fc`] = true;
          
          b.floors.forEach((f, fIdx) => {
            if (!f.students || Number(f.students) < 0) errs[`b_${bIdx}_f_${fIdx}_s`] = true;
            if (!f.staff || Number(f.staff) < 0) errs[`b_${bIdx}_f_${fIdx}_st`] = true;
            if (!f.admins || Number(f.admins) < 0) errs[`b_${bIdx}_f_${fIdx}_a`] = true;
          });
        });
      }
    } else {
      if (!form.dcRacks) errs.dcRacks = 'Required';
      if (!form.dcServers) errs.dcServers = 'Required';
    }
    return errs;
  }

  /* --- Campus Sync Logic --- */
  function updateBuildingCount(count) {
    const n = Math.max(0, Math.min(20, parseInt(count) || 0));
    setForm(prev => {
      const buildings = [...prev.buildings];
      // Add new buildings if count increased
      while (buildings.length < n) {
        buildings.push({ 
          id: crypto.randomUUID(), 
          name: '', 
          floorCount: '', 
          floors: [] 
        });
      }
      return { ...prev, buildingCount: count, buildings: buildings.slice(0, n) };
    });
  }

  function updateBuildingMeta(bIdx, field, val) {
    setForm(prev => {
      const buildings = [...prev.buildings];
      buildings[bIdx][field] = val;
      
      // If floor count changed, sync the floors array
      if (field === 'floorCount') {
        const fn = Math.max(0, Math.min(50, parseInt(val) || 0));
        const floors = [...buildings[bIdx].floors];
        while (floors.length < fn) {
          floors.push({ name: '', students: '', staff: '', admins: '' });
        }
        buildings[bIdx].floors = floors.slice(0, fn);
      }
      
      return { ...prev, buildings };
    });
  }

  function updateFloor(bIdx, fIdx, field, val) {
    setForm(prev => {
      const buildings = [...prev.buildings];
      buildings[bIdx].floors[fIdx][field] = val;
      return { ...prev, buildings };
    });
  }

  async function handleSubmit(e) {
    e.preventDefault();
    const errs = validate();
    setErrors(errs);
    if (Object.keys(errs).length > 0) {
      window.alert('All primary input fields are compulsory! Please fill them before proceeding.');
      // Scroll to top so user sees the first error
      window.scrollTo({ top: 0, behavior: 'smooth' });
      return;
    }
    setSubmitting(true);
    dispatch({ type: 'UPDATE_REQUIREMENTS', payload: form });
    try {
      const design = await submitRequirements(form);
      dispatch({ type: 'SET_PROPOSED_DESIGN', payload: design });
      navigate('/design');
    } catch (err) { console.error('Submit failed:', err); }
    finally { setSubmitting(false); }
  }

  return (
    <div className="h-full overflow-y-auto p-8 custom-scrollbar">
      <form onSubmit={handleSubmit} className="max-w-4xl mx-auto pb-24">
        {/* Back button to switch solution type */}
        <button type="button" onClick={() => navigate('/solution-type')}
          className="flex items-center gap-2 text-on-surface-variant hover:text-primary transition-colors mb-6 group">
          <span className="material-symbols-outlined text-lg group-hover:-translate-x-1 transition-transform">arrow_back</span>
          <span className="text-sm font-medium">Back to Solution Type</span>
        </button>

      <header className="mb-10">
        <div className="flex items-center gap-2 text-primary mb-2">
          <span className="material-symbols-outlined text-sm">edit_note</span>
          <span className="text-xs font-[family-name:var(--font-mono)] uppercase tracking-[0.2em]">
            {isCampus ? 'Campus Setup' : 'Data Center Setup'}
          </span>
        </div>
        <h1 className="text-3xl font-bold font-[family-name:var(--font-headline)] text-on-surface tracking-tight">
          {isCampus ? 'Tell us about your campus' : 'Tell us about your data center'}
        </h1>
        <p className="text-on-surface-variant mt-2 max-w-2xl">
          Answer a few simple questions. Our AI will design the perfect network for you.
        </p>

        {/* Validation error banner */}
        {Object.keys(errors).length > 0 && (
          <div className="mt-4 p-4 bg-error/10 border border-error/30 rounded-lg flex items-center gap-3">
            <span className="material-symbols-outlined text-error">error</span>
            <span className="text-sm text-error font-medium">Please fill in all required fields before proceeding.</span>
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
              />
            </div>
          </Section>

          {Number(form.buildingCount) > 0 && (
            <Section title="Building Details" icon="edit_square">
              <p className="text-on-surface-variant text-sm mb-6">Tell us the name and number of floors for each building.</p>
              <div className="space-y-4">
                {form.buildings.map((b, i) => (
                  <div key={b.id} className="grid grid-cols-1 md:grid-cols-3 gap-4 bg-surface-container-low p-4 rounded-xl border border-outline-variant/20 items-end">
                    <div className="md:col-span-2 space-y-2">
                      <label className="text-xs font-bold text-primary uppercase">Building {i + 1} Name</label>
                      <input 
                        type="text" 
                        placeholder="e.g. Main Block, Library, Hostel"
                        value={b.name}
                        onChange={(e) => updateBuildingMeta(i, 'name', e.target.value)}
                        className={`w-full bg-surface-container-highest border rounded-lg px-4 py-2 text-on-surface focus:ring-1 focus:ring-primary outline-none transition-all ${
                          errors[`b_${i}_name`] ? 'border-error' : 'border-outline-variant/30'
                        }`}
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-xs font-bold text-primary uppercase">Number of Floors</label>
                      <input 
                        type="number" 
                        min="1"
                        placeholder="e.g. 3"
                        value={b.floorCount}
                        onChange={(e) => updateBuildingMeta(i, 'floorCount', e.target.value)}
                        className={`w-full bg-surface-container-highest border rounded-lg px-4 py-2 text-on-surface focus:ring-1 focus:ring-primary outline-none transition-all ${
                          errors[`b_${i}_fc`] ? 'border-error' : 'border-outline-variant/30'
                        }`}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </Section>
          )}

          {form.buildings.some(b => b.name && Number(b.floorCount) > 0) && (
            <Section title="Who will use the network?" icon="group">
              <p className="text-on-surface-variant text-sm mb-6">Enter the user counts for each floor. All fields are mandatory.</p>
              
              <div className="space-y-12">
                {form.buildings.filter(b => b.name && Number(b.floorCount) > 0).map((building) => {
                  const bIdx = form.buildings.findIndex(b => b.id === building.id);
                  return (
                    <div key={building.id} className="space-y-4">
                      <div className="flex items-center gap-2 text-primary border-l-4 border-primary pl-4 py-1">
                        <span className="material-symbols-outlined">domain</span>
                        <h3 className="font-bold text-lg">{building.name}</h3>
                        <span className="text-xs text-on-surface-variant bg-surface-container px-2 py-0.5 rounded ml-2">
                          {building.floorCount} Floors
                        </span>
                      </div>

                      <div className="overflow-x-auto border border-outline-variant/10 rounded-xl bg-surface-container-low shadow-sm">
                        <table className="w-full text-sm">
                          <thead className="bg-surface-container text-on-surface-variant">
                            <tr>
                              <th className="px-4 py-3 text-left font-medium w-48">Floor Name</th>
                              <th className="px-4 py-3 text-left font-medium">Students*</th>
                              <th className="px-4 py-3 text-left font-medium">Staff*</th>
                              <th className="px-4 py-3 text-left font-medium">Admins*</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-outline-variant/10">
                            {building.floors.map((floor, fIdx) => {
                              const rowError = errors[`b_${bIdx}_f_${fIdx}_s`] || errors[`b_${bIdx}_f_${fIdx}_st`] || errors[`b_${bIdx}_f_${fIdx}_a`];
                              return (
                                <tr key={fIdx} className={`transition-colors ${rowError ? 'bg-error/5' : ''}`}>
                                  <td className="px-4 py-2">
                                    <input 
                                      type="text" 
                                      placeholder={fIdx === 0 ? 'Ground Floor' : `Floor ${fIdx}`}
                                      value={floor.name}
                                      onChange={(e) => updateFloor(bIdx, fIdx, 'name', e.target.value)}
                                      className="w-full bg-transparent border-b border-transparent focus:border-primary px-1 py-1 outline-none"
                                    />
                                  </td>
                                  <td className="px-4 py-2">
                                    <input 
                                      type="number" 
                                      min="0"
                                      placeholder="0"
                                      value={floor.students}
                                      onChange={(e) => updateFloor(bIdx, fIdx, 'students', e.target.value)}
                                      className={`w-full bg-surface-container-highest rounded-md px-3 py-2 border transition-all ${
                                        errors[`b_${bIdx}_f_${fIdx}_s`] ? 'border-error ring-1 ring-error/20' : 'border-outline-variant/20 focus:border-primary'
                                      }`}
                                    />
                                  </td>
                                  <td className="px-4 py-2">
                                    <input 
                                      type="number" 
                                      min="0"
                                      placeholder="0"
                                      value={floor.staff}
                                      onChange={(e) => updateFloor(bIdx, fIdx, 'staff', e.target.value)}
                                      className={`w-full bg-surface-container-highest rounded-md px-3 py-2 border transition-all ${
                                        errors[`b_${bIdx}_f_${fIdx}_st`] ? 'border-error ring-1 ring-error/20' : 'border-outline-variant/20 focus:border-primary'
                                      }`}
                                    />
                                  </td>
                                  <td className="px-4 py-2">
                                    <input 
                                      type="number" 
                                      min="0"
                                      placeholder="0"
                                      value={floor.admins}
                                      onChange={(e) => updateFloor(bIdx, fIdx, 'admins', e.target.value)}
                                      className={`w-full bg-surface-container-highest rounded-md px-3 py-2 border transition-all ${
                                        errors[`b_${bIdx}_f_${fIdx}_a`] ? 'border-error ring-1 ring-error/20' : 'border-outline-variant/20 focus:border-primary'
                                      }`}
                                    />
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                          <tfoot className="bg-surface-container/50">
                            <tr className="font-bold text-primary">
                              <td className="px-4 py-3 text-xs uppercase tracking-wider text-on-surface-variant">Building Total</td>
                              <td className="px-4 py-3">{building.floors.reduce((s, f) => s + (Number(f.students) || 0), 0)}</td>
                              <td className="px-4 py-3">{building.floors.reduce((s, f) => s + (Number(f.staff) || 0), 0)}</td>
                              <td className="px-4 py-3">{building.floors.reduce((s, f) => s + (Number(f.admins) || 0), 0)}</td>
                            </tr>
                          </tfoot>
                        </table>
                      </div>
                    </div>
                  );
                })}
              </div>
            </Section>
          )}

          <Section title="What devices do you have?" icon="devices">
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              {campusDevices.map(d => (
                <DeviceToggle key={d.key} {...d} active={form.devices[d.key]} onClick={() => toggleDevice(d.key)} />
              ))}
            </div>
          </Section>

          <Section title="Special Roles & Areas" icon="security">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              <div>
                <label className="text-sm font-medium text-on-surface-variant mb-4 block">Key Personnel Roles</label>
                <div className="flex flex-wrap gap-2">
                  {campusRoles.map(role => (
                    <ChipToggle key={role} label={role} active={form.specialRoles.includes(role)} onClick={() => toggleRole(role)} />
                  ))}
                </div>
              </div>
              <div>
                <label className="text-sm font-medium text-on-surface-variant mb-4 block">Sensitive Areas (High Security)</label>
                <div className="grid grid-cols-2 gap-3">
                  {campusSensitiveAreas.map(area => (
                    <AreaToggle key={area.id} {...area} active={form.sensitiveAreas.includes(area.id)} onClick={() => toggleArea(area.id)} />
                  ))}
                </div>
              </div>
            </div>
          </Section>
        </>
      )}

      {/* ========== DATA CENTER-SPECIFIC SECTIONS ========== */}
      {!isCampus && (
        <>
          <Section title="About Your Facility" icon="warehouse">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <NumberInput label="How many server racks?" value={form.dcRacks} onChange={v => set('dcRacks', v)} placeholder="e.g. 10" error={errors.dcRacks} />
              <NumberInput label="How many servers (approx)?" value={form.dcServers} onChange={v => set('dcServers', v)} placeholder="e.g. 50" error={errors.dcServers} />
            </div>
          </Section>

          <Section title="What's it used for?" icon="apps">
            <p className="text-on-surface-variant text-sm mb-4">Select all that apply.</p>
            <div className="flex flex-wrap gap-2">
              {['Web Hosting', 'Database Storage', 'Application Servers', 'File Storage', 'Email Services', 'Video Streaming', 'AI / Machine Learning', 'Backup & Disaster Recovery'].map(use => (
                <ChipToggle key={use} label={use} active={form.specialRoles.includes(use)} onClick={() => toggleRole(use)} />
              ))}
            </div>
          </Section>

          <Section title="What equipment do you have?" icon="memory">
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              {dcEquipment.map(d => (
                <DeviceToggle key={d.key} {...d} active={form.devices[d.key]} onClick={() => toggleDevice(d.key)} />
              ))}
            </div>
          </Section>

          <Section title="Security zones" icon="shield">
            <p className="text-on-surface-variant text-sm mb-4">Select which zones need separate network segments.</p>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              {dcSecurityZones.map(area => (
                <AreaToggle key={area.id} {...area} active={form.sensitiveAreas.includes(area.id)} onClick={() => toggleArea(area.id)} />
              ))}
            </div>
          </Section>
        </>
      )}

      {/* ========== SHARED SECTIONS (both types) ========== */}

      <Section title="How important is network uptime?" icon="speed">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[
            { val: 'standard', label: 'Standard', desc: 'Occasional brief outages are acceptable', color: 'tertiary' },
            { val: 'important', label: 'Important', desc: 'Minimal downtime, critical for daily operations', color: 'primary' },
            { val: 'critical', label: 'Mission Critical', desc: '24/7 availability, no downtime allowed', color: 'error' },
          ].map(opt => (
            <button type="button" key={opt.val} onClick={() => set('uptimeLevel', opt.val)}
              className={`p-5 rounded-xl border text-left transition-all ${
                form.uptimeLevel === opt.val
                  ? `bg-${opt.color}/10 border-${opt.color}/40`
                  : 'bg-surface-container-low border-outline-variant/15 hover:border-outline-variant/30'
              }`}>
              <div className={`text-sm font-bold ${form.uptimeLevel === opt.val ? `text-${opt.color}` : 'text-on-surface'}`}>{opt.label}</div>
              <div className="text-xs text-on-surface-variant mt-1">{opt.desc}</div>
            </button>
          ))}
        </div>
      </Section>

      <Section title="Future plans" icon="trending_up">
        <div className="flex items-center gap-4 mb-4">
          <label className="text-sm font-medium text-on-surface-variant">
            {isCampus ? 'Do you expect your campus to grow?' : 'Do you expect to add more capacity?'}
          </label>
          <button type="button" onClick={() => set('expectGrowth', !form.expectGrowth)}
            className={`w-12 h-6 rounded-full transition-all relative ${form.expectGrowth ? 'bg-primary' : 'bg-surface-container-highest'}`}>
            <div className={`w-5 h-5 rounded-full bg-white absolute top-0.5 transition-transform ${form.expectGrowth ? 'translate-x-6' : 'translate-x-0.5'}`} />
          </button>
        </div>
        {form.expectGrowth && (
          <select value={form.growthAmount} onChange={e => set('growthAmount', e.target.value)}
            className="bg-surface-container-low border border-outline-variant/30 rounded-lg px-4 py-3 text-on-surface focus:ring-1 focus:ring-primary w-full md:w-64">
            <option value="">{isCampus ? 'How many more people?' : 'How much more capacity?'}</option>
            <option value="<50">{isCampus ? 'Less than 50 people' : '1-5 more racks'}</option>
            <option value="50-200">{isCampus ? '50 – 200 people' : '5-15 more racks'}</option>
            <option value="200-500">{isCampus ? '200 – 500 people' : '15-30 more racks'}</option>
            <option value="500+">{isCampus ? 'More than 500 people' : '30+ more racks'}</option>
          </select>
        )}
      </Section>

      <Section title="Anything else?" icon="chat">
        <textarea value={form.additionalNotes} onChange={e => set('additionalNotes', e.target.value)} rows={4}
          className="w-full bg-surface-container-low border border-outline-variant/30 rounded-lg px-4 py-3 text-on-surface placeholder:text-outline/50 focus:ring-1 focus:ring-primary resize-none"
          placeholder={isCampus
            ? "Describe anything else. E.g. 'We have a library with 50 computers, a hostel block, and want CCTV in parking areas.'"
            : "Describe anything else. E.g. 'We need 10Gbps uplinks between racks and a separate management network.'"
          }
        />
      </Section>

      {/* Submit */}
      <div className="fixed bottom-0 left-0 right-0 bg-surface/80 backdrop-blur-md border-t border-outline-variant/15 p-4 flex justify-end z-30">
        <button type="submit" disabled={submitting}
          className="px-8 py-3 bg-gradient-to-r from-primary to-primary-container text-on-primary font-bold rounded-lg shadow-lg shadow-primary/20 hover:brightness-110 active:scale-[0.98] transition-all flex items-center gap-3 disabled:opacity-50 mr-4">
          <span className="material-symbols-outlined">auto_awesome</span>
          {submitting ? 'Generating...' : 'Generate My Network Design'}
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
          <span className="material-symbols-outlined text-primary text-lg">{icon}</span>
        </div>
        <h2 className="text-lg font-bold font-[family-name:var(--font-headline)] text-on-surface">{title}</h2>
      </div>
      {children}
    </section>
  );
}

function NumberInput({ label, value, onChange, placeholder, error }) {
  return (
    <div className="space-y-2">
      <label className="text-sm font-medium text-on-surface-variant">{label}</label>
      <input type="number" min="0" value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder}
        className={`w-full bg-surface-container-low border rounded-lg px-4 py-3 text-on-surface placeholder:text-outline/50 focus:ring-1 focus:ring-primary focus:border-primary transition-colors ${
          error ? 'border-error/60 ring-1 ring-error/20' : 'border-outline-variant/30'
        }`} />
      {error && <span className="text-[10px] text-error font-medium uppercase tracking-wider">{error}</span>}
    </div>
  );
}

function ChipToggle({ label, active, onClick }) {
  return (
    <button type="button" onClick={onClick}
      className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${
        active ? 'bg-primary/20 text-primary border border-primary/40' : 'bg-surface-container-high text-on-surface-variant border border-transparent hover:border-outline-variant/30'
      }`}>
      {label}
    </button>
  );
}

function DeviceToggle({ icon, label, active, onClick }) {
  return (
    <button type="button" onClick={onClick}
      className={`flex flex-col items-center gap-2 p-4 rounded-xl border transition-all text-center ${
        active ? 'bg-primary/10 border-primary/40 text-primary' : 'bg-surface-container-low border-outline-variant/15 text-on-surface-variant hover:border-outline-variant/30'
      }`}>
      <span className="text-2xl">{icon}</span>
      <span className="text-xs font-medium">{label}</span>
    </button>
  );
}

function AreaToggle({ icon, label, active, onClick }) {
  return (
    <button type="button" onClick={onClick}
      className={`flex items-center gap-3 p-4 rounded-xl border transition-all text-left ${
        active ? 'bg-tertiary/10 border-tertiary/40' : 'bg-surface-container-low border-outline-variant/15 hover:border-outline-variant/30'
      }`}>
      <span className="text-2xl">{icon}</span>
      <span className="text-sm font-medium text-on-surface">{label}</span>
    </button>
  );
}
