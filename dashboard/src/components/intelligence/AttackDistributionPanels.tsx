"use client";

import { useState } from "react";
import { BrainCircuit, ShieldAlert } from "lucide-react";
import CollapsiblePanel from "@/components/ui/CollapsiblePanel";

interface AttackDistributionPanelsProps {
  attackTypesExpanded: boolean;
  mitreExpanded: boolean;
  onToggleAttackTypes: () => void;
  onToggleMitre: () => void;
  attackTypes: Array<{ name: string; value: number; fill: string }>;
  totalAttacks: number;
  mitreData: Array<{ name: string; count: number }>;
}

type HoverTooltip = {
  name: string;
  count: number;
  x: number;
  y: number;
  alignRight: boolean;
};

export default function AttackDistributionPanels({
  attackTypesExpanded,
  mitreExpanded,
  onToggleAttackTypes,
  onToggleMitre,
  attackTypes,
  totalAttacks,
  mitreData,
}: AttackDistributionPanelsProps) {
  const [hoveredAttack, setHoveredAttack] = useState<HoverTooltip | null>(null);
  const [hoveredMitre, setHoveredMitre] = useState<HoverTooltip | null>(null);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
      <CollapsiblePanel
        expanded={attackTypesExpanded}
        onToggle={onToggleAttackTypes}
        icon={ShieldAlert}
        iconColor="text-red-500"
        title="Attack Types Distribution"
        summary={`${totalAttacks} Events`}
      >
        <div
          className="h-[200px] group-data-[fullscreen=true]/fs:h-[60vh] w-full flex flex-col items-center justify-center gap-4 relative"
          onMouseLeave={() => setHoveredAttack(null)}
        >
          <div className="relative h-32 w-32 group-data-[fullscreen=true]/fs:h-64 group-data-[fullscreen=true]/fs:w-64 transition-all duration-300 shrink-0">
            <svg viewBox="-1 -1 2 2" className="w-full h-full" style={{ transform: "rotate(-90deg)" }}>
              {totalAttacks > 0 ? (() => {
                let cumulativePercent = 0;
                return attackTypes.map((item) => {
                  const slicePercent = Number(item.value || 0) / totalAttacks;
                  if (slicePercent === 0) return null;
                  const handleMouseMove = (e: React.MouseEvent) => {
                    setHoveredAttack({
                      name: item.name,
                      count: Number(item.value),
                      x: e.clientX,
                      y: e.clientY,
                      alignRight: e.clientX > window.innerWidth / 2,
                    });
                  };
                  if (slicePercent === 1) {
                    return <circle key={item.name} r="1" cx="0" cy="0" fill={item.fill} onMouseMove={handleMouseMove} className="hover:opacity-80 transition-opacity cursor-crosshair" />;
                  }
                  const startX = Math.cos(2 * Math.PI * cumulativePercent);
                  const startY = Math.sin(2 * Math.PI * cumulativePercent);
                  cumulativePercent += slicePercent;
                  const endX = Math.cos(2 * Math.PI * cumulativePercent);
                  const endY = Math.sin(2 * Math.PI * cumulativePercent);
                  const largeArcFlag = slicePercent > 0.5 ? 1 : 0;
                  const pathData = `M ${startX} ${startY} A 1 1 0 ${largeArcFlag} 1 ${endX} ${endY} L 0 0`;
                  return <path key={item.name} d={pathData} fill={item.fill} className="hover:opacity-80 transition-opacity cursor-crosshair" onMouseMove={handleMouseMove} />;
                });
              })() : <circle r="1" cx="0" cy="0" fill="#334155" />}
            </svg>
            <div className="absolute inset-[24%] rounded-full bg-white dark:bg-[#0a0a0a] flex flex-col items-center justify-center pointer-events-none transition-all duration-300">
              <span className="text-xl group-data-[fullscreen=true]/fs:text-4xl font-bold text-slate-900 dark:text-white leading-none transition-all duration-300">{totalAttacks}</span>
            </div>
          </div>
          <div className="flex flex-wrap justify-center gap-x-4 gap-y-1">
            {attackTypes.map((item) => (
              <div key={item.name} className="flex items-center gap-1.5 text-[11px] text-slate-600 dark:text-slate-400">
                <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: item.fill }} />
                <span>{item.name}</span>
              </div>
            ))}
          </div>
          {hoveredAttack && (
            <div
              className="fixed pointer-events-none z-[9999] px-3 py-2 bg-[#0a0a0a] border border-white/10 rounded-lg shadow-xl text-[11px] text-white flex flex-col gap-1 whitespace-nowrap"
              style={{
                left: hoveredAttack.alignRight ? undefined : hoveredAttack.x + 15,
                right: hoveredAttack.alignRight ? (window.innerWidth - hoveredAttack.x + 15) : undefined,
                top: hoveredAttack.y + 15,
              }}
            >
              <span className="text-slate-400 font-medium">{hoveredAttack.name}</span>
              <span className="font-bold text-red-400">{hoveredAttack.count} Attacks</span>
            </div>
          )}
        </div>
      </CollapsiblePanel>

      <CollapsiblePanel
        expanded={mitreExpanded}
        onToggle={onToggleMitre}
        icon={BrainCircuit}
        iconColor="text-blue-500"
        title="MITRE ATT&CK Mapping"
        summary={`${mitreData.length} Techniques Mapped`}
      >
        <div
          className="h-[200px] group-data-[fullscreen=true]/fs:h-[60vh] w-full space-y-3 overflow-y-auto pr-2 terminal-scrollbar relative"
          onMouseLeave={() => setHoveredMitre(null)}
        >
          {mitreData.length === 0 ? (
            <div className="text-xs text-slate-500 text-center h-full flex items-center justify-center">No MITRE techniques in selected window.</div>
          ) : mitreData.map((item) => {
            const width = `${Math.round((item.count / Math.max(1, mitreData.length)) * 100)}%`;
            return (
              <div
                key={item.name}
                className="grid grid-cols-[100px_1fr_30px] items-center gap-2 text-xs hover:bg-slate-50 dark:hover:bg-white/5 p-1 rounded-sm cursor-crosshair transition-colors"
                onMouseMove={(e) => {
                  setHoveredMitre({
                    name: item.name,
                    count: item.count,
                    x: e.clientX,
                    y: e.clientY,
                    alignRight: e.clientX > window.innerWidth / 2,
                  });
                }}
              >
                <span className="text-[10px] text-slate-500 truncate">{item.name}</span>
                <div className="h-2 rounded bg-slate-100 dark:bg-white/10 overflow-hidden pointer-events-none">
                  <div className="h-full rounded bg-blue-500" style={{ width }} />
                </div>
                <span className="font-mono text-[10px] text-slate-700 dark:text-slate-300 text-right pointer-events-none">{item.count}</span>
              </div>
            );
          })}
          {hoveredMitre && (
            <div
              className="fixed pointer-events-none z-[9999] px-3 py-2 bg-[#0a0a0a] border border-white/10 rounded-lg shadow-xl text-[11px] text-white flex flex-col gap-1 whitespace-nowrap"
              style={{
                left: hoveredMitre.alignRight ? undefined : hoveredMitre.x + 15,
                right: hoveredMitre.alignRight ? (window.innerWidth - hoveredMitre.x + 15) : undefined,
                top: hoveredMitre.y + 15,
              }}
            >
              <span className="text-slate-400 font-medium">{hoveredMitre.name}</span>
              <span className="font-bold text-blue-400">{hoveredMitre.count} Hits</span>
            </div>
          )}
        </div>
      </CollapsiblePanel>
    </div>
  );
}
