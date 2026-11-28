"use client";

import { useMemo, useState } from "react";
import CollapsiblePanel from "@/components/ui/CollapsiblePanel";
import { Server } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import CustomDropdown from "@/components/ui/CustomDropdown";

const CHART_ROW_HEIGHT = 24;
const CHART_MIN_HEIGHT = 200;
const CHART_MAX_HEIGHT = "70vh";
const LABEL_COLUMN_WIDTH = 120;
const LABEL_MAX_CHARS = 18;

interface NetworkStatsPanelProps {
  expanded: boolean;
  onToggle: () => void;
  isps: { name: string; count: number }[];
}

export default function NetworkStatsPanel({ expanded, onToggle, isps }: NetworkStatsPanelProps) {
  const [mode, setMode] = useState<"most" | "least">("most");

  const displayData = useMemo(() => {
    if (mode === "most") {
      return [...isps];
    }
    return [...isps].reverse();
  }, [isps, mode]);

  const chartHeight = Math.max(CHART_MIN_HEIGHT, displayData.length * CHART_ROW_HEIGHT);

  const topIsp = isps.length > 0 ? isps[0].name : "None";

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
      icon={Server}
      iconColor="text-emerald-500"
      title="Attack Networks"
      summary={`Top: ${topIsp}`}
    >
      <div className="flex justify-between items-center mb-4">
        <span className="text-xs text-slate-500">All Source Networks</span>
        <CustomDropdown
          options={[
            { label: "Most Attacks", value: "most" },
            { label: "Least Attacks", value: "least" },
          ]}
          value={mode}
          onChange={(v) => setMode(v as "most" | "least")}
          className="w-32"
        />
      </div>
      <div
        className="w-full text-xs overflow-y-auto terminal-scrollbar"
        style={{ height: chartHeight, maxHeight: CHART_MAX_HEIGHT }}
      >
        {displayData.length === 0 ? (
          <div className="h-full flex items-center justify-center text-slate-500">No network data available</div>
        ) : (
          <div style={{ height: chartHeight }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={displayData} layout="vertical" margin={{ top: 0, right: 6, left: 0, bottom: 0 }}>
              <XAxis type="number" hide domain={[0, "dataMax"]} />
              <YAxis
                dataKey="name"
                type="category"
                axisLine={false}
                tickLine={false}
                tick={{ fontSize: 10, fill: "#64748b" }}
                width={LABEL_COLUMN_WIDTH}
                tickFormatter={(value) => {
                  const label = String(value);
                  const text = label.length > LABEL_MAX_CHARS ? `${label.slice(0, LABEL_MAX_CHARS - 1)}...` : label;
                  return text.replace(/ /g, "\u00A0");
                }}
              />
              <Tooltip
                cursor={{ fill: "rgba(255, 255, 255, 0.05)" }}
                contentStyle={{ backgroundColor: "#0a0a0a", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "8px", fontSize: "11px" }}
                itemStyle={{ color: "#fff" }}
                formatter={(value) => [formatTooltipValue(value), "Attacks"]}
              />
              <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                {displayData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill="#10b981" />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          </div>
        )}
      </div>
    </CollapsiblePanel>
  );
}
