import React from "react";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
} from "recharts";

const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#06b6d4"];

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg p-3 text-sm shadow-xl">
      <p className="text-slate-300 font-medium mb-1">{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color }} className="text-xs">
          {p.name}: <span className="font-medium">{typeof p.value === "number" ? p.value.toLocaleString() : p.value}</span>
        </p>
      ))}
    </div>
  );
};

function SuccessRateByPhase({ data }) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
        <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 12 }} />
        <YAxis tick={{ fill: "#94a3b8", fontSize: 12 }} unit="%" domain={[0, 100]} />
        <Tooltip content={<CustomTooltip />} />
        <Bar dataKey="success_rate" name="Success Rate %" radius={[4, 4, 0, 0]}>
          {data.map((_, i) => (
            <Cell key={i} fill={COLORS[i % COLORS.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function SuccessRateByArea({ data }) {
  const sorted = [...data].sort((a, b) => b.success_rate - a.success_rate);
  return (
    <ResponsiveContainer width="100%" height={320}>
      <BarChart data={sorted} layout="vertical" margin={{ top: 5, right: 20, left: 120, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
        <XAxis type="number" tick={{ fill: "#94a3b8", fontSize: 12 }} unit="%" domain={[0, 100]} />
        <YAxis type="category" dataKey="name" tick={{ fill: "#94a3b8", fontSize: 11 }} width={110} />
        <Tooltip content={<CustomTooltip />} />
        <Bar dataKey="success_rate" name="Success Rate %" radius={[0, 4, 4, 0]}>
          {sorted.map((_, i) => (
            <Cell key={i} fill={COLORS[i % COLORS.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function EnrollmentDistribution({ data }) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
        <XAxis dataKey="bucket" tick={{ fill: "#94a3b8", fontSize: 12 }} />
        <YAxis yAxisId="left" tick={{ fill: "#94a3b8", fontSize: 12 }} />
        <YAxis yAxisId="right" orientation="right" tick={{ fill: "#94a3b8", fontSize: 12 }} unit="%" />
        <Tooltip content={<CustomTooltip />} />
        <Legend wrapperStyle={{ color: "#94a3b8", fontSize: 12 }} />
        <Bar yAxisId="left" dataKey="total" name="Total Trials" fill="#3b82f6" radius={[4, 4, 0, 0]} />
        <Bar yAxisId="right" dataKey="success_rate" name="Success Rate %" fill="#10b981" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

function TrialVolumeOverTime({ data }) {
  const formatted = data.map((d) => ({
    ...d,
    year: d.year ? new Date(d.year).getFullYear() : d.year,
  }));
  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={formatted} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
        <XAxis dataKey="year" tick={{ fill: "#94a3b8", fontSize: 12 }} />
        <YAxis tick={{ fill: "#94a3b8", fontSize: 12 }} />
        <Tooltip content={<CustomTooltip />} />
        <Legend wrapperStyle={{ color: "#94a3b8", fontSize: 12 }} />
        <Line type="monotone" dataKey="total" name="Total Trials" stroke="#3b82f6" strokeWidth={2} dot={false} />
        {formatted[0]?.successes !== undefined && (
          <Line type="monotone" dataKey="successes" name="Successful" stroke="#10b981" strokeWidth={2} dot={false} />
        )}
      </LineChart>
    </ResponsiveContainer>
  );
}

function SponsorComparison({ data }) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
        <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 12 }} />
        <YAxis yAxisId="left" tick={{ fill: "#94a3b8", fontSize: 12 }} />
        <YAxis yAxisId="right" orientation="right" unit="%" tick={{ fill: "#94a3b8", fontSize: 12 }} />
        <Tooltip content={<CustomTooltip />} />
        <Legend wrapperStyle={{ color: "#94a3b8", fontSize: 12 }} />
        <Bar yAxisId="left" dataKey="total" name="Total Trials" fill="#3b82f6" radius={[4, 4, 0, 0]} />
        <Bar yAxisId="right" dataKey="success_rate" name="Success Rate %" fill="#10b981" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

function DurationVsSuccess({ data }) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
        <XAxis dataKey="bucket" tick={{ fill: "#94a3b8", fontSize: 12 }} />
        <YAxis tick={{ fill: "#94a3b8", fontSize: 12 }} unit="%" domain={[0, 100]} />
        <Tooltip content={<CustomTooltip />} />
        <Bar dataKey="success_rate" name="Success Rate %" radius={[4, 4, 0, 0]}>
          {data.map((_, i) => (
            <Cell key={i} fill={COLORS[i % COLORS.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

const CHART_TITLES = {
  success_rate_by_phase: "Success Rate by Trial Phase",
  success_rate_by_area: "Success Rate by Therapeutic Area",
  enrollment_distribution: "Enrollment Size Distribution",
  trial_volume_over_time: "Trial Volume Over Time",
  sponsor_comparison: "Sponsor Type Comparison",
  duration_vs_success: "Trial Duration vs. Success Rate",
};

export default function ChartRenderer({ chartData }) {
  if (!chartData?.data?.length) {
    return (
      <div className="text-slate-500 text-sm text-center py-8">No chart data available</div>
    );
  }

  const { chart_type, data } = chartData;
  const title = CHART_TITLES[chart_type] || chart_type;

  let ChartComponent;
  switch (chart_type) {
    case "success_rate_by_phase": ChartComponent = <SuccessRateByPhase data={data} />; break;
    case "success_rate_by_area": ChartComponent = <SuccessRateByArea data={data} />; break;
    case "enrollment_distribution": ChartComponent = <EnrollmentDistribution data={data} />; break;
    case "trial_volume_over_time": ChartComponent = <TrialVolumeOverTime data={data} />; break;
    case "sponsor_comparison": ChartComponent = <SponsorComparison data={data} />; break;
    case "duration_vs_success": ChartComponent = <DurationVsSuccess data={data} />; break;
    default:
      return <div className="text-slate-500 text-sm">Unknown chart type: {chart_type}</div>;
  }

  return (
    <div className="mt-4 bg-slate-900 border border-slate-800 rounded-xl p-4">
      <h3 className="text-sm font-semibold text-slate-300 mb-3">{title}</h3>
      {ChartComponent}
      <p className="text-xs text-slate-600 mt-2 text-right">{data.length} data points</p>
    </div>
  );
}
