import React, { useState } from "react";
import { predictCustom, predictByNctId } from "../api/client";
import { FlaskConical, Loader2, CheckCircle, XCircle, AlertCircle } from "lucide-react";

const PHASES = ["PHASE1", "PHASE2", "PHASE3", "PHASE4", "EARLY_PHASE1"];
const SPONSOR_CLASSES = ["INDUSTRY", "NIH", "OTHER_GOV", "INDIVIDUAL"];
const THERAPEUTIC_AREAS = [
  "Oncology", "Cardiology", "Neurology", "Psychiatry", "Endocrinology",
  "Infectious Disease", "Respiratory", "Rheumatology", "Nephrology", "Other",
];
const INTERVENTION_TYPES = ["DRUG", "BIOLOGICAL", "DEVICE", "PROCEDURE", "BEHAVIORAL", "OTHER"];

export default function PredictPage() {
  const [tab, setTab] = useState("custom"); // custom | nctid
  const [nctId, setNctId] = useState("");
  const [form, setForm] = useState({
    phase: "PHASE3",
    sponsor_class: "INDUSTRY",
    therapeutic_area: "Oncology",
    intervention_types: ["DRUG"],
    enrollment: 300,
    duration_days: 730,
    number_of_arms: 2,
    locations_count: 20,
    countries: ["United States"],
    eligibility_min_age: 18,
    eligibility_max_age: 75,
  });
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handlePredict = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = tab === "nctid"
        ? await predictByNctId(nctId.trim())
        : await predictCustom(form);
      setResult(data);
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    } finally {
      setLoading(false);
    }
  };

  const probaPct = result ? Math.round(result.success_probability * 100) : 0;

  return (
    <div className="overflow-y-auto h-screen p-6">
      <div className="max-w-2xl mx-auto">
        <div className="mb-6">
          <h1 className="text-xl font-bold text-white">Trial Success Predictor</h1>
          <p className="text-sm text-slate-400 mt-1">
            Enter trial design parameters or an NCT ID to get an AI-powered success prediction.
          </p>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 p-1 bg-slate-900 rounded-lg mb-6 border border-slate-800">
          {[["custom", "Design Parameters"], ["nctid", "By NCT ID"]].map(([key, label]) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`flex-1 text-sm py-2 rounded-md font-medium transition-colors ${
                tab === key ? "bg-brand-600 text-white" : "text-slate-400 hover:text-white"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {tab === "nctid" ? (
          <div className="card mb-6">
            <label className="text-sm text-slate-400 block mb-2">NCT ID</label>
            <input
              value={nctId}
              onChange={(e) => setNctId(e.target.value)}
              placeholder="e.g. NCT01234567"
              className="input w-full"
            />
            <p className="text-xs text-slate-600 mt-2">
              The trial must already be in the TrialMind database.
            </p>
          </div>
        ) : (
          <div className="card mb-6 space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs text-slate-400 block mb-1.5">Phase</label>
                <select
                  value={form.phase}
                  onChange={(e) => setForm((f) => ({ ...f, phase: e.target.value }))}
                  className="input w-full"
                >
                  {PHASES.map((p) => <option key={p}>{p}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-slate-400 block mb-1.5">Sponsor Type</label>
                <select
                  value={form.sponsor_class}
                  onChange={(e) => setForm((f) => ({ ...f, sponsor_class: e.target.value }))}
                  className="input w-full"
                >
                  {SPONSOR_CLASSES.map((s) => <option key={s}>{s}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-slate-400 block mb-1.5">Therapeutic Area</label>
                <select
                  value={form.therapeutic_area}
                  onChange={(e) => setForm((f) => ({ ...f, therapeutic_area: e.target.value }))}
                  className="input w-full"
                >
                  {THERAPEUTIC_AREAS.map((a) => <option key={a}>{a}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-slate-400 block mb-1.5">Intervention Type</label>
                <select
                  value={form.intervention_types[0] || "DRUG"}
                  onChange={(e) => setForm((f) => ({ ...f, intervention_types: [e.target.value] }))}
                  className="input w-full"
                >
                  {INTERVENTION_TYPES.map((t) => <option key={t}>{t}</option>)}
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              {[
                ["Enrollment (patients)", "enrollment", 1, 100000],
                ["Duration (days)", "duration_days", 30, 5000],
                ["Number of arms", "number_of_arms", 1, 10],
                ["Number of sites", "locations_count", 1, 2000],
                ["Min age (years)", "eligibility_min_age", 0, 100],
                ["Max age (years)", "eligibility_max_age", 0, 100],
              ].map(([label, key, min, max]) => (
                <div key={key}>
                  <label className="text-xs text-slate-400 block mb-1.5">{label}</label>
                  <input
                    type="number"
                    min={min}
                    max={max}
                    value={form[key]}
                    onChange={(e) => setForm((f) => ({ ...f, [key]: parseInt(e.target.value) || 0 }))}
                    className="input w-full"
                  />
                </div>
              ))}
            </div>
          </div>
        )}

        <button
          onClick={handlePredict}
          disabled={loading || (tab === "nctid" && !nctId.trim())}
          className="btn-primary w-full flex items-center justify-center gap-2 py-3"
        >
          {loading ? (
            <><Loader2 size={18} className="animate-spin" /> Predicting…</>
          ) : (
            <><FlaskConical size={18} /> Predict Success Probability</>
          )}
        </button>

        {error && (
          <div className="mt-4 bg-red-900/20 border border-red-800 text-red-300 text-sm rounded-xl px-4 py-3">
            {error}
          </div>
        )}

        {/* Result */}
        {result && (
          <div className="mt-6 card space-y-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">Prediction</p>
                <div className="flex items-center gap-2">
                  {result.predicted_success ? (
                    <CheckCircle size={20} className="text-green-400" />
                  ) : (
                    <XCircle size={20} className="text-red-400" />
                  )}
                  <span className={`text-lg font-bold ${result.predicted_success ? "text-green-300" : "text-red-300"}`}>
                    {result.predicted_success ? "Likely to Succeed" : "At Risk of Failure"}
                  </span>
                </div>
              </div>
              <div className="text-right">
                <p className="text-xs text-slate-500 mb-1">Confidence</p>
                <span className={`badge text-xs px-2.5 py-1 ${
                  result.confidence === "High" ? "bg-green-900/30 text-green-300 border border-green-800" :
                  result.confidence === "Medium" ? "bg-yellow-900/30 text-yellow-300 border border-yellow-800" :
                  "bg-slate-800 text-slate-400 border border-slate-700"
                }`}>
                  {result.confidence} confidence
                </span>
              </div>
            </div>

            {/* Probability bar */}
            <div>
              <div className="flex justify-between text-xs text-slate-400 mb-1.5">
                <span>Failure risk</span>
                <span className="font-medium text-white">{probaPct}% success probability</span>
                <span>Success likelihood</span>
              </div>
              <div className="h-3 bg-slate-800 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${
                    probaPct >= 60 ? "bg-green-500" : probaPct >= 40 ? "bg-yellow-500" : "bg-red-500"
                  }`}
                  style={{ width: `${probaPct}%` }}
                />
              </div>
            </div>

            {/* Contributing features */}
            {result.top_contributing_features?.length > 0 && (
              <div>
                <p className="text-xs text-slate-500 uppercase tracking-wider mb-3">
                  Top Contributing Factors
                </p>
                <div className="space-y-2">
                  {result.top_contributing_features.map((f, i) => (
                    <div key={i} className="flex items-center justify-between">
                      <span className="text-sm text-slate-300">{f.feature.replace(/_/g, " ")}</span>
                      <div className="flex items-center gap-2">
                        <div className="w-24 bg-slate-800 rounded-full h-1.5">
                          <div
                            className="h-1.5 rounded-full bg-brand-500"
                            style={{
                              width: `${(f.importance / result.top_contributing_features[0].importance) * 100}%`,
                            }}
                          />
                        </div>
                        <span className="text-xs text-slate-500 w-12 text-right">
                          {f.importance.toFixed(4)}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="flex items-start gap-2 text-xs text-slate-600 pt-2 border-t border-slate-800">
              <AlertCircle size={13} className="flex-shrink-0 mt-0.5" />
              <span>
                This prediction is generated by an ML model trained on historical ClinicalTrials.gov data.
                It is intended for research purposes only and should not guide clinical or regulatory decisions.
                Model: {result.model_version}
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
