import React, { useEffect, useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { getBenchmark, getBenchmarkByPhase, getBenchmarkByArea, getModelInfo } from "../api/client";
import { CheckCircle, XCircle, Target, TrendingUp, Loader2 } from "lucide-react";

const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899"];

function MetricCard({ label, value, sub, icon: Icon, color = "blue" }) {
  const colorMap = {
    blue: "text-blue-400 bg-blue-400/10",
    green: "text-green-400 bg-green-400/10",
    yellow: "text-yellow-400 bg-yellow-400/10",
    purple: "text-purple-400 bg-purple-400/10",
  };
  return (
    <div className="card flex items-start gap-4">
      <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${colorMap[color]}`}>
        <Icon size={20} />
      </div>
      <div>
        <p className="text-2xl font-bold text-white">{value}</p>
        <p className="text-sm text-slate-400">{label}</p>
        {sub && <p className="text-xs text-slate-600 mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

function ConfusionMatrix({ data }) {
  const { tp, tn, fp, fn } = data;
  const total = tp + tn + fp + fn;
  return (
    <div className="card">
      <h3 className="text-sm font-semibold text-slate-300 mb-4">Confusion Matrix</h3>
      <div className="grid grid-cols-2 gap-2 max-w-xs">
        {[
          { label: "True Positive", value: tp, bg: "bg-green-900/30 border-green-800", text: "text-green-300" },
          { label: "False Positive", value: fp, bg: "bg-red-900/20 border-red-900", text: "text-red-300" },
          { label: "False Negative", value: fn, bg: "bg-yellow-900/20 border-yellow-900", text: "text-yellow-300" },
          { label: "True Negative", value: tn, bg: "bg-green-900/30 border-green-800", text: "text-green-300" },
        ].map((cell) => (
          <div key={cell.label} className={`rounded-lg border p-3 ${cell.bg}`}>
            <p className={`text-xl font-bold ${cell.text}`}>{cell.value.toLocaleString()}</p>
            <p className="text-xs text-slate-500 mt-0.5">{cell.label}</p>
            <p className="text-xs text-slate-600">{((cell.value / total) * 100).toFixed(1)}%</p>
          </div>
        ))}
      </div>
      <p className="text-xs text-slate-600 mt-3">Total samples: {total.toLocaleString()}</p>
    </div>
  );
}

export default function BenchmarkPage() {
  const [benchmark, setBenchmark] = useState(null);
  const [byPhase, setByPhase] = useState([]);
  const [byArea, setByArea] = useState([]);
  const [modelInfo, setModelInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([
      getBenchmark({ limit: 1000 }),
      getBenchmarkByPhase(),
      getBenchmarkByArea(),
      getModelInfo(),
    ])
      .then(([b, bp, ba, mi]) => {
        setBenchmark(b);
        setByPhase(bp || []);
        setByArea(ba || []);
        setModelInfo(mi);
      })
      .catch((e) => setError(e.response?.data?.error || e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <Loader2 size={32} className="animate-spin text-brand-400" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 max-w-xl">
        <div className="bg-red-900/20 border border-red-800 rounded-xl p-5 text-red-300 text-sm">
          <p className="font-medium mb-1">Could not load benchmark data</p>
          <p className="text-red-400/70">{error}</p>
          <p className="mt-3 text-xs text-red-400/50">
            Make sure the ML service is running and the model has been trained with{" "}
            <code className="font-mono">python train.py</code>.
          </p>
        </div>
      </div>
    );
  }

  const cm = benchmark?.confusion_matrix;
  const accuracy = benchmark ? `${(benchmark.accuracy * 100).toFixed(1)}%` : "—";

  return (
    <div className="overflow-y-auto h-screen p-6">
      <div className="max-w-5xl mx-auto">
        <div className="mb-6">
          <h1 className="text-xl font-bold text-white">Model Accuracy Benchmark</h1>
          <p className="text-sm text-slate-400 mt-1">
            Performance of the XGBoost trial-success predictor on held-out historical trials
            {modelInfo && ` · Model ${modelInfo.model_version}`}
          </p>
        </div>

        {/* Key metrics */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <MetricCard label="Overall Accuracy" value={accuracy} icon={Target} color="blue" sub={`${benchmark?.n_samples?.toLocaleString()} test samples`} />
          {modelInfo && (
            <>
              <MetricCard label="AUC-ROC" value={(modelInfo.auc_roc * 100).toFixed(1) + "%"} icon={TrendingUp} color="green" />
              <MetricCard label="F1 Score" value={(modelInfo.f1_score * 100).toFixed(1) + "%"} icon={CheckCircle} color="purple" />
              <MetricCard label="Precision" value={(modelInfo.precision_score * 100).toFixed(1) + "%"} icon={CheckCircle} color="yellow" />
            </>
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          {cm && <ConfusionMatrix data={cm} />}

          {/* Feature importance */}
          {modelInfo?.feature_importance && (
            <div className="card">
              <h3 className="text-sm font-semibold text-slate-300 mb-4">Top Feature Importances (SHAP)</h3>
              <div className="space-y-2">
                {Object.entries(modelInfo.feature_importance)
                  .slice(0, 8)
                  .map(([feature, importance], i) => (
                    <div key={feature}>
                      <div className="flex justify-between text-xs text-slate-400 mb-1">
                        <span>{feature.replace(/_/g, " ")}</span>
                        <span>{importance.toFixed(4)}</span>
                      </div>
                      <div className="w-full bg-slate-800 rounded-full h-1.5">
                        <div
                          className="h-1.5 rounded-full"
                          style={{
                            width: `${(importance / Object.values(modelInfo.feature_importance)[0]) * 100}%`,
                            backgroundColor: COLORS[i % COLORS.length],
                          }}
                        />
                      </div>
                    </div>
                  ))}
              </div>
            </div>
          )}
        </div>

        {/* By phase */}
        {byPhase.length > 0 && (
          <div className="card mb-6">
            <h3 className="text-sm font-semibold text-slate-300 mb-4">Prediction Accuracy by Trial Phase</h3>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={byPhase}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="phase" tick={{ fill: "#94a3b8", fontSize: 12 }} />
                <YAxis tick={{ fill: "#94a3b8", fontSize: 12 }} unit="%" domain={[0, 100]} />
                <Tooltip
                  contentStyle={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: 8 }}
                  labelStyle={{ color: "#cbd5e1" }}
                  itemStyle={{ color: "#94a3b8" }}
                  formatter={(v) => [`${(v * 100).toFixed(1)}%`, "Accuracy"]}
                />
                <Bar dataKey="accuracy" name="Accuracy" radius={[4, 4, 0, 0]}>
                  {byPhase.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* By area */}
        {byArea.length > 0 && (
          <div className="card mb-6">
            <h3 className="text-sm font-semibold text-slate-300 mb-4">Prediction Accuracy by Therapeutic Area</h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={byArea} layout="vertical" margin={{ left: 110 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis type="number" tick={{ fill: "#94a3b8", fontSize: 12 }} unit="%" domain={[0, 100]} />
                <YAxis type="category" dataKey="area" tick={{ fill: "#94a3b8", fontSize: 11 }} width={100} />
                <Tooltip
                  contentStyle={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: 8 }}
                  formatter={(v) => [`${(v * 100).toFixed(1)}%`, "Accuracy"]}
                />
                <Bar dataKey="accuracy" name="Accuracy" radius={[0, 4, 4, 0]}>
                  {byArea.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
}
