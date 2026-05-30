"use client";

import CollapsiblePanel from "./CollapsiblePanel";
import { AlertTriangle } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";

interface RiskScorePanelProps {
  expanded: boolean;
  onToggle: () => void;
  risk: { buckets: number[]; avg: number };
}

const LABELS = ["0-20", "20-40", "40-60", "60-80", "80-100"];
const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#f97316", "#ef4444"];

export default function RiskScorePanel({ expanded, onToggle, risk }: RiskScorePanelProps) {
  const data = risk.buckets.map((count, i) => ({
    range: LABELS[i],
    count,
    color: COLORS[i]
  }));

  const formatTooltipValue = (value: unknown): number | string => {
    if (Array.isArray(value) && value.length > 0) {
      return String(value[0] ?? 0);
    }
    if (typeof value === "number" || typeof value === "string") {
      return value;
    }
    return 0;
  };

  return (
    <CollapsiblePanel
      expanded={expanded}
      onToggle={onToggle}
      icon={AlertTriangle}
      iconColor="text-orange-500"
      title="Risk Score Distribution"
      summary={`Avg Score: ${risk.avg.toFixed(1)}`}
    >
      <div className="h-[200px] group-data-[fullscreen=true]/fs:h-[60vh] w-full text-xs pt-4">
        {risk.buckets.every(b => b === 0) ? (
          <div className="h-full flex items-center justify-center text-slate-500">No risk scores calculated</div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 0, right: 0, left: -20, bottom: 20 }}>
              <XAxis dataKey="range" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#64748b' }} dy={10} />
              <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#64748b' }} />
              <Tooltip
                cursor={{ fill: 'rgba(255, 255, 255, 0.05)' }}
                contentStyle={{ backgroundColor: '#0a0a0a', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', fontSize: '11px' }}
                itemStyle={{ color: '#fff' }}
                formatter={(value) => [formatTooltipValue(value), "Sessions"]}
              />
              <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                {data.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </CollapsiblePanel>
  );
}
