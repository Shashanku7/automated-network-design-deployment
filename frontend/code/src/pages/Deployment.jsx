/**
 * Deployment — Final review & execute
 *
 * Plain-English confirmation checklist (no ACL/VLAN jargon).
 * Simple progress indicators. Technical logs hidden by default.
 */
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useProject } from "../context/ProjectContext";
import { triggerDeployment } from "../services/api";
import { renderMd } from "../utils/renderMd";

export default function Deployment() {
  const navigate = useNavigate();
  const { projectId } = useParams();
  const { state, dispatch } = useProject();
  const [confirmed, setConfirmed] = useState(false);
  const [showLogs, setShowLogs] = useState(false);
  const [deploying, setDeploying] = useState(false);

  const design = state.proposedDesign;
  const bom = design?.bom || [];

  async function handleDeploy() {
    if (!confirmed) return;
    setDeploying(true);
    dispatch({ type: "SET_DEPLOYMENT_STATUS", payload: "executing" });

    try {
      await triggerDeployment("PROJ-001");
      dispatch({ type: "SET_DEPLOYMENT_STATUS", payload: "complete" });
    } catch (err) {
      console.error("Deploy error:", err);
    }
    setDeploying(false);
  }

  const isComplete = state.deploymentStatus === "complete";

  return (
    <div className="h-full overflow-y-auto p-8 custom-scrollbar">
      <div className="max-w-6xl mx-auto">
        <header className="mb-10">
          <div className="flex items-center gap-2 text-primary mb-2">
            <span className="material-symbols-outlined text-sm">
              rocket_launch
            </span>
            <span className="text-xs font-[family-name:var(--font-mono)] uppercase tracking-[0.2em]">
              Final Step
            </span>
          </div>
          <h1 className="text-3xl font-bold font-[family-name:var(--font-headline)] text-on-surface tracking-tight">
            Review & Deploy
          </h1>
          <p className="text-on-surface-variant mt-2">
            Review your network design before finalizing.
          </p>
        </header>

        <div className="grid grid-cols-12 gap-8">
          {/* Left: Summary */}
          <div className="col-span-12 lg:col-span-8 space-y-6">
            {/* Design Summary — Plain English */}
            <section className="bg-surface-container-low rounded-xl border border-outline-variant/15 p-6">
              <h3 className="text-lg font-bold font-[family-name:var(--font-headline)] mb-4 flex items-center gap-2">
                <span className="material-symbols-outlined text-primary">
                  summarize
                </span>
                Design Summary
              </h3>
              <div className="space-y-3">
                {bom.map((item, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-3 p-3 bg-surface rounded-lg"
                  >
                    <span
                      className="material-symbols-outlined text-tertiary"
                      style={{ fontVariationSettings: "'FILL' 1" }}
                    >
                      check_circle
                    </span>
                    <div className="flex-1">
                      <div className="text-sm font-medium">
                        {item.product} × {item.qty}
                      </div>
                      <div className="text-xs text-on-surface-variant">
                        {item.purpose}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </section>

            {/* CLI Config — Phase 5 output */}
            {state.cliConfig && (
              <section className="bg-surface-container-low rounded-xl border border-outline-variant/15 overflow-hidden">
                <div className="p-6">
                  <h3 className="text-lg font-bold font-[family-name:var(--font-headline)] mb-4 flex items-center gap-2">
                    <span className="material-symbols-outlined text-primary">
                      terminal
                    </span>
                    CLI Configuration
                  </h3>
                  <div
                    className="md-content text-sm text-on-surface leading-relaxed"
                    dangerouslySetInnerHTML={{
                      __html: renderMd(state.cliConfig),
                    }}
                  />
                </div>
              </section>
            )}

            {/* Technical Logs (hidden by default) */}
            <div>
              <button
                onClick={() => setShowLogs(!showLogs)}
                className="text-sm text-on-surface-variant flex items-center gap-2 hover:text-on-surface transition-colors mb-2"
              >
                <span className="material-symbols-outlined text-sm">
                  {showLogs ? "expand_less" : "expand_more"}
                </span>
                {showLogs ? "Hide" : "Show"} Technical Logs
              </button>
              {showLogs && (
                <div className="bg-surface-dim rounded-xl border border-outline-variant/10 p-4 font-[family-name:var(--font-mono)] text-xs leading-relaxed text-on-surface-variant max-h-48 overflow-y-auto">
                  <p>
                    <span className="text-outline/50">[INFO]</span>{" "}
                    <span className="text-primary-dim">
                      Initializing deployment engine v2.4.0
                    </span>
                  </p>
                  <p>
                    <span className="text-outline/50">[INFO]</span> Connecting
                    to network devices...{" "}
                    <span className="text-tertiary">OK</span>
                  </p>
                  <p>
                    <span className="text-outline/50">[INFO]</span> Validating
                    configuration integrity...
                  </p>
                  <p>
                    <span className="text-outline/50">[INFO]</span> Waiting for
                    administrator confirmation...
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Right: Confirmation & Deploy */}
          <div className="col-span-12 lg:col-span-4 space-y-6">
            {/* Readiness */}
            <section className="bg-surface-container-low rounded-xl p-6 border border-outline-variant/15">
              <h3 className="text-sm font-bold uppercase tracking-wider text-on-surface-variant mb-4 flex items-center gap-2">
                <span className="material-symbols-outlined text-primary text-sm">
                  verified
                </span>
                Readiness
              </h3>
              <div className="space-y-3">
                {[
                  "Design Generated",
                  "Equipment Selected",
                  "Configuration Ready",
                ].map((item) => (
                  <div key={item} className="flex items-center gap-3 p-2">
                    <span
                      className="material-symbols-outlined text-tertiary text-sm"
                      style={{ fontVariationSettings: "'FILL' 1" }}
                    >
                      check_circle
                    </span>
                    <span className="text-sm">{item}</span>
                  </div>
                ))}
                <div className="flex items-center gap-3 p-2">
                  <span
                    className={`material-symbols-outlined text-sm ${confirmed ? "text-tertiary" : "text-outline"}`}
                    style={
                      confirmed ? { fontVariationSettings: "'FILL' 1" } : {}
                    }
                  >
                    {confirmed ? "check_circle" : "pending"}
                  </span>
                  <span className="text-sm">Your Confirmation</span>
                </div>
              </div>
            </section>

            {/* Confirmation & Deploy Button */}
            <section className="bg-surface-container-highest rounded-xl p-6 border border-primary/20 relative overflow-hidden">
              <div className="absolute -top-12 -right-12 w-32 h-32 bg-primary/10 blur-[40px] rounded-full" />
              <h3 className="text-lg font-bold mb-4">Final Confirmation</h3>
              <label className="flex items-start gap-3 cursor-pointer mb-6">
                <input
                  type="checkbox"
                  checked={confirmed}
                  onChange={(e) => setConfirmed(e.target.checked)}
                  className="mt-1 rounded border-outline-variant bg-surface-container text-primary focus:ring-primary/20"
                />
                <span className="text-sm text-on-surface-variant leading-relaxed">
                  I confirm that the proposed design meets my requirements and
                  I'm ready to proceed.
                </span>
              </label>
              <button
                onClick={handleDeploy}
                disabled={!confirmed || deploying || isComplete}
                className="w-full py-4 bg-gradient-to-r from-primary to-primary-container text-on-primary font-extrabold uppercase tracking-widest text-sm rounded-lg shadow-lg shadow-primary/20 hover:brightness-110 active:scale-[0.98] transition-all flex items-center justify-center gap-3 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <span className="material-symbols-outlined">
                  {isComplete ? "check_circle" : "rocket_launch"}
                </span>
                {isComplete
                  ? "Deployment Complete!"
                  : deploying
                    ? "Deploying..."
                    : "Execute Deployment"}
              </button>
            </section>

            {isComplete && (
              <button
                onClick={() => navigate("/")}
                className="w-full py-3 border border-outline-variant/30 text-on-surface font-medium rounded-lg hover:bg-surface-container-high transition-all text-center"
              >
                Return to Dashboard
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
