"use client";

import { useState, useRef } from "react";
import CollapsiblePanel from "./CollapsiblePanel";
import { Shield } from "lucide-react";

interface SoarBreakdownPanelProps {
  expanded: boolean;
  onToggle: () => void;
  soar: { data: { name: string; value: number }[]; blockRate: number; blockedCount: number };
}

const COLORS = {
  iptables_block: "#ef4444",
  already_blocked: "#f97316",
  detect_only: "#f59e0b",
  dry_run_block: "#3b82f6",
  none: "#64748b"
};

export default function SoarBreakdownPanel({ expanded, onToggle, soar }: SoarBreakdownPanelProps) {
  const totalActions = soar.data.reduce((acc, item) => acc + (item.value || 0), 0);
  const [hovered, setHovered] = useState<{ name: string, count: number, x: number, y: number, alignRight: boolean } | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  return (
    <CollapsiblePanel
      expanded={expanded}
      onToggle={onToggle}
      icon={Shield}
      iconColor="text-red-500"
      title="SOAR Response Breakdown"
      summary={`Block Rate: ${soar.blockRate}%`}
    >
      <div className="h-[200px] group-data-[fullscreen=true]/fs:h-[60vh] w-full flex flex-col items-center justify-center gap-4 relative" ref={containerRef} onMouseLeave={() => setHovered(null)}>
        <div className="relative h-32 w-32 group-data-[fullscreen=true]/fs:h-64 group-data-[fullscreen=true]/fs:w-64 transition-all duration-300 shrink-0">
          <svg viewBox="-1 -1 2 2" className="w-full h-full" style={{ transform: "rotate(-90deg)" }}>
            {totalActions > 0 ? (() => {
              let cumulativePercent = 0;
              return soar.data.map((item) => {
                const slicePercent = Number(item.value || 0) / totalActions;
                if (slicePercent === 0) return null;
                const fill = COLORS[item.name as keyof typeof COLORS] || "#64748b";
                
                const handleMouseMove = (e: React.MouseEvent) => {
                  setHovered({ 
                    name: item.name, 
                    count: item.value, 
                    x: e.clientX, 
                    y: e.clientY,
                    alignRight: e.clientX > window.innerWidth / 2
                  });
                };

                if (slicePercent === 1) {
                  return <circle key={item.name} r="1" cx="0" cy="0" fill={fill} onMouseMove={handleMouseMove} className="hover:opacity-80 transition-opacity cursor-crosshair" />;
                }
                const startX = Math.cos(2 * Math.PI * cumulativePercent);
                const startY = Math.sin(2 * Math.PI * cumulativePercent);
                cumulativePercent += slicePercent;
                const endX = Math.cos(2 * Math.PI * cumulativePercent);
                const endY = Math.sin(2 * Math.PI * cumulativePercent);
                const largeArcFlag = slicePercent > 0.5 ? 1 : 0;
                const pathData = `M ${startX} ${startY} A 1 1 0 ${largeArcFlag} 1 ${endX} ${endY} L 0 0`;
                return <path key={item.name} d={pathData} fill={fill} className="hover:opacity-80 transition-opacity cursor-crosshair" onMouseMove={handleMouseMove} />;
              });
            })() : <circle r="1" cx="0" cy="0" fill="#334155" />}
          </svg>
          <div className="absolute inset-[24%] rounded-full bg-white dark:bg-[#0a0a0a] flex flex-col items-center justify-center pointer-events-none transition-all duration-300">
            <span className="text-xl group-data-[fullscreen=true]/fs:text-4xl font-bold text-slate-900 dark:text-white leading-none transition-all duration-300">{totalActions}</span>
            <span className="text-[10px] group-data-[fullscreen=true]/fs:text-sm font-medium text-slate-500 mt-1 transition-all duration-300">Actions</span>
          </div>
        </div>
        <div className="flex flex-wrap justify-center gap-x-4 gap-y-1">
          {soar.data.map((item) => (
            <div key={item.name} className="flex items-center gap-1.5 text-[11px] text-slate-600 dark:text-slate-400">
              <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: COLORS[item.name as keyof typeof COLORS] || "#64748b" }} />
              <span>{item.name}</span>
            </div>
          ))}
        </div>
        {hovered && (
          <div 
            className="fixed pointer-events-none z-[9999] px-3 py-2 bg-[#0a0a0a] border border-white/10 rounded-lg shadow-xl text-[11px] text-white flex flex-col gap-1 whitespace-nowrap"
            style={{ 
              left: hovered.alignRight ? undefined : hovered.x + 15,
              right: hovered.alignRight ? (window.innerWidth - hovered.x + 15) : undefined,
              top: hovered.y + 15 
            }}
          >
            <span className="text-slate-400 font-medium">{hovered.name}</span>
            <span className="font-bold text-red-400">{hovered.count} Actions</span>
          </div>
        )}
      </div>
    </CollapsiblePanel>
  );
}
