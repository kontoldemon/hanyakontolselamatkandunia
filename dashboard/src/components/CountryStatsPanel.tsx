"use client";

import { useMemo, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import CollapsiblePanel from "./CollapsiblePanel";
import { Globe } from "lucide-react";
import CustomDropdown from "./CustomDropdown";

interface CountryStatsPanelProps {
  expanded: boolean;
  onToggle: () => void;
  countries: { code: string; name: string; count: number }[];
}

export default function CountryStatsPanel({ expanded, onToggle, countries }: CountryStatsPanelProps) {
  const [mode, setMode] = useState<"most" | "least">("most");

  const formatTooltipValue = (value: unknown): number | string => {
    if (Array.isArray(value) && value.length > 0) {
      return String(value[0] ?? 0);
    }
    if (typeof value === "number" || typeof value === "string") {
      return value;
    }
    return 0;
  };

  const displayData = useMemo(() => {
    if (mode === "most") {
      return [...countries].slice(0, 10);
    }
    return [...countries].reverse().slice(0, 10);
  }, [countries, mode]);

  const topCountry = countries.length > 0 ? countries[0].name : "None";

  return (
    <CollapsiblePanel
      expanded={expanded}
      onToggle={onToggle}
      icon={Globe}
      iconColor="text-blue-500"
      title="Attacker Countries"
      summary={`${countries.length} countries | Top: ${topCountry}`}
    >
      <div className="flex justify-between items-center mb-4">
        <span className="text-xs text-slate-500">Top 10 Source Countries</span>
        <CustomDropdown
          options={[
            { label: "Most Attacks", value: "most" },
            { label: "Least Attacks", value: "least" }
          ]}
          value={mode}
          onChange={(v) => setMode(v as "most" | "least")}
          className="w-32"
        />
      </div>
      <div className="h-[200px] group-data-[fullscreen=true]/fs:h-[60vh] w-full text-xs">
        {displayData.length === 0 ? (
          <div className="h-full flex items-center justify-center text-slate-500">No country data available</div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={displayData} layout="vertical" margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <XAxis type="number" hide />
              <YAxis dataKey="name" type="category" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: "#64748b" }} width={80} />
              <Tooltip
                cursor={{ fill: "rgba(255, 255, 255, 0.05)" }}
                contentStyle={{ backgroundColor: "#0a0a0a", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "8px", fontSize: "11px" }}
                itemStyle={{ color: "#fff" }}
                formatter={(value) => [formatTooltipValue(value), "Attacks"]}
              />
              <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                {displayData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={mode === "most" ? "#3b82f6" : "#f59e0b"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </CollapsiblePanel>
  );
}
