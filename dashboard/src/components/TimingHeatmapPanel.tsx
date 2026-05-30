"use client";

import { useState } from "react";
import CollapsiblePanel from "./CollapsiblePanel";
import { Clock } from "lucide-react";

interface TimingHeatmapPanelProps {
  expanded: boolean;
  onToggle: () => void;
  heatmap: { grid: number[][]; max: number; peakHour: number };
}

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const HOURS = Array.from({ length: 24 }, (_, i) => i);

export default function TimingHeatmapPanel({ expanded, onToggle, heatmap }: TimingHeatmapPanelProps) {
  const [hovered, setHovered] = useState<{ day: string, hour: string, count: number, x: number, y: number, alignRight: boolean } | null>(null);

  const formatHour = (h: number) => {
    if (h === 0) return "12A";
    if (h === 12) return "12P";
    return h > 12 ? `${h - 12}P` : `${h}A`;
  };

  const peakFormat = formatHour(heatmap.peakHour);

  return (
    <CollapsiblePanel
      expanded={expanded}
      onToggle={onToggle}
      icon={Clock}
      iconColor="text-purple-500"
      title="Attack Timing Heatmap"
      summary={`Peak activity: ${peakFormat}`}
    >
      <div className="flex justify-between items-center mb-4 h-7">
        <span className="text-xs text-slate-500">7-Day Hourly Activity</span>
      </div>
      <div className="h-[200px] group-data-[fullscreen=true]/fs:h-[60vh] w-full overflow-x-auto terminal-scrollbar pb-2 relative flex flex-col justify-center">
        <div className="min-w-[600px] flex flex-col gap-1 relative h-full" onMouseLeave={() => setHovered(null)}>
          <div className="grid grid-cols-[30px_repeat(24,1fr)] gap-1 mb-1">
            <div />
            {HOURS.map(h => (
              <div key={h} className="text-[9px] text-slate-500 text-center">{formatHour(h)}</div>
            ))}
          </div>
          {heatmap.grid.map((row, dayIdx) => (
            <div key={dayIdx} className="grid grid-cols-[30px_repeat(24,1fr)] gap-1 flex-1">
              <div className="text-[10px] text-slate-500 flex items-center pr-2">{DAYS[dayIdx]}</div>
              {row.map((val, hourIdx) => {
                const intensity = heatmap.max > 0 ? val / heatmap.max : 0;
                let bgColor = "bg-slate-100 dark:bg-white/5";
                if (intensity > 0) {
                  if (intensity < 0.2) bgColor = "bg-purple-200 dark:bg-purple-900/30";
                  else if (intensity < 0.5) bgColor = "bg-purple-300 dark:bg-purple-800/50";
                  else if (intensity < 0.8) bgColor = "bg-purple-400 dark:bg-purple-600/70";
                  else bgColor = "bg-purple-500 dark:bg-purple-500";
                }
                return (
                  <div
                    key={hourIdx}
                    onMouseMove={(e) => {
                      setHovered({
                        day: DAYS[dayIdx],
                        hour: formatHour(hourIdx),
                        count: val,
                        x: e.clientX,
                        y: e.clientY,
                        alignRight: e.clientX > window.innerWidth / 2
                      });
                    }}
                    className={`w-full h-full min-h-[20px] rounded-sm ${bgColor} transition-all hover:ring-1 hover:ring-purple-400 cursor-crosshair`}
                  />
                );
              })}
            </div>
          ))}

          {hovered && (
            <div 
              className="fixed pointer-events-none z-[9999] px-3 py-2 bg-[#0a0a0a] border border-white/10 rounded-lg shadow-xl text-[11px] text-white flex flex-col gap-1 whitespace-nowrap"
              style={{ 
                left: hovered.alignRight ? undefined : hovered.x + 15,
                right: hovered.alignRight ? (window.innerWidth - hovered.x + 15) : undefined,
                top: hovered.y + 15 
              }}
            >
              <span className="text-slate-400 font-medium">{hovered.day} {hovered.hour}</span>
              <span className="font-bold text-purple-400">{hovered.count} Attacks</span>
            </div>
          )}
        </div>
      </div>
    </CollapsiblePanel>
  );
}
