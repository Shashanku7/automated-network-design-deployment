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
      if (!form.buildings) errs.buildings = 'Required';
      if (!form.students) errs.students = 'Required';
      if (!form.staff) errs.staff = 'Required';
      if (!form.admins) errs.admins = 'Required';
    } else {
      if (!form.buildings) errs.buildings = 'Required';  // racks for DC
      if (!form.students) errs.students = 'Required';    // servers for DC
    }
    return errs;
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
          <Section title="About Your Campus" icon="apartment">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <NumberInput label="How many buildings?" value={form.buildings} onChange={v => set('buildings', v)} placeholder="e.g. 4" error={errors.buildings} />
              <div className="space-y-2">
                <label className="text-sm font-medium text-on-surface-variant">Floors per building (approx)</label>
                <select value={form.floorsPerBuilding} onChange={e => set('floorsPerBuilding', e.target.value)}
                  className="w-full bg-surface-container-low border border-outline-variant/30 rounded-lg px-4 py-3 text-on-surface focus:ring-1 focus:ring-primary focus:border-primary">
                  {['1', '2', '3', '4', '5'].map(f => <option key={f} value={f}>{f === '5' ? '5+ Floors' : `${f} Floor${f > 1 ? 's' : ''}`}</option>)}
                </select>
              </div>
            </div>
          </Section>

          <Section title="Who will use the network?" icon="group">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <NumberInput label="Students / Visitors" value={form.students} onChange={v => set('students', v)} placeholder="e.g. 500" error={errors.students} />
              <NumberInput label="Staff / Faculty" value={form.staff} onChange={v => set('staff', v)} placeholder="e.g. 50" error={errors.staff} />
              <NumberInput label="Administrators" value={form.admins} onChange={v => set('admins', v)} placeholder="e.g. 10" error={errors.admins} />
            </div>
            <div className="mt-6">
              <label className="text-sm font-medium text-on-surface-variant mb-3 block">Any special roles?</label>
              <div className="flex flex-wrap gap-2">
                {campusRoles.map(role => (
                  <ChipToggle key={role} label={role} active={form.specialRoles.includes(role)} onClick={() => toggleRole(role)} />
                ))}
              </div>
            </div>
          </Section>

          <Section title="What devices do you have?" icon="devices">
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              {campusDevices.map(d => (
                <DeviceToggle key={d.key} {...d} active={form.devices[d.key]} onClick={() => toggleDevice(d.key)} />
              ))}
            </div>
          </Section>

          <Section title="Do you have any sensitive areas?" icon="shield">
            <p className="text-on-surface-variant text-sm mb-4">Select areas that need extra security.</p>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              {campusSensitiveAreas.map(area => (
                <AreaToggle key={area.id} {...area} active={form.sensitiveAreas.includes(area.id)} onClick={() => toggleArea(area.id)} />
              ))}
            </div>
          </Section>
        </>
      )}

      {/* ========== DATA CENTER-SPECIFIC SECTIONS ========== */}
      {!isCampus && (
        <>
          <Section title="About Your Facility" icon="warehouse">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <NumberInput label="How many server racks?" value={form.buildings} onChange={v => set('buildings', v)} placeholder="e.g. 10" error={errors.buildings} />
              <NumberInput label="How many servers (approx)?" value={form.students} onChange={v => set('students', v)} placeholder="e.g. 50" error={errors.students} />
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
      <div className="fixed bottom-0 left-64 right-0 bg-surface/80 backdrop-blur-md border-t border-outline-variant/15 p-4 flex justify-end z-30">
        <button type="submit" disabled={submitting}
          className="px-8 py-3 bg-gradient-to-r from-primary to-primary-container text-on-primary font-bold rounded-lg shadow-lg shadow-primary/20 hover:brightness-110 active:scale-[0.98] transition-all flex items-center gap-3 disabled:opacity-50">
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
