"use client";

import { Fingerprint, ShieldAlert } from "lucide-react";
import CollapsiblePanel from "@/components/ui/CollapsiblePanel";
import CustomDropdown from "@/components/ui/CustomDropdown";

interface FingerprintsPanelProps {
  expanded: boolean;
  onToggle: () => void;
  fingerprints: Array<{ hash: string; client: string; count: number }>;
}

export function FingerprintsPanel({ expanded, onToggle, fingerprints }: FingerprintsPanelProps) {
  return (
    <CollapsiblePanel
      expanded={expanded}
      onToggle={onToggle}
      icon={Fingerprint}
      iconColor="text-purple-500"
      title="HASSH Fingerprints"
      summary={`${fingerprints.length} Signatures`}
    >
      <div className="h-[300px] overflow-y-auto border border-slate-100 dark:border-white/5 rounded-md">
        <table className="w-full text-left">
          <thead className="bg-slate-50 dark:bg-white/5 text-[10px] text-slate-500 sticky top-0 backdrop-blur-md">
            <tr>
              <th className="px-4 py-2 font-medium">Hash</th>
              <th className="px-4 py-2 font-medium">Client Info</th>
              <th className="px-4 py-2 font-medium w-16 text-right">Count</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-white/5 text-xs">
            {fingerprints.length === 0 ? (
              <tr><td className="px-4 py-3 text-slate-500 text-center" colSpan={3}>No fingerprints captured.</td></tr>
            ) : fingerprints.map((item) => (
              <tr className="hover:bg-slate-50 dark:hover:bg-white/5" key={item.hash}>
                <td className="px-4 py-2 font-mono text-[10px] text-slate-500">{item.hash}</td>
                <td className="px-4 py-2 text-blue-500 font-mono text-[10px] truncate max-w-[120px]" title={item.client}>{item.client}</td>
                <td className="px-4 py-2 text-slate-500 font-mono text-right">{item.count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </CollapsiblePanel>
  );
}

interface CommandsAndPasswordsPanelsProps {
  commandsExpanded: boolean;
  passwordsExpanded: boolean;
  onToggleCommands: () => void;
  onTogglePasswords: () => void;
  commandMode: "most" | "least";
  onCommandModeChange: (mode: "most" | "least") => void;
  commandSearch: string;
  onCommandSearchChange: (search: string) => void;
  pagedCommands: Array<{ command: string; count: number }>;
  uniqueCommandCount: number;
  commandCurrentPage: number;
  commandTotalPages: number;
  pageSize: number;
  pageNumbers: number[];
  onCommandPageChange: (page: number) => void;
  passwordWords: Array<{ word: string; count: number }>;
  maxPasswordCount: number;
}

export function CommandsAndPasswordsPanels({
  commandsExpanded,
  passwordsExpanded,
  onToggleCommands,
  onTogglePasswords,
  commandMode,
  onCommandModeChange,
  commandSearch,
  onCommandSearchChange,
  pagedCommands,
  uniqueCommandCount,
  commandCurrentPage,
  commandTotalPages,
  pageSize,
  pageNumbers,
  onCommandPageChange,
  passwordWords,
  maxPasswordCount,
}: CommandsAndPasswordsPanelsProps) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
      <CollapsiblePanel
        expanded={commandsExpanded}
        onToggle={onToggleCommands}
        icon={ShieldAlert}
        iconColor="text-amber-500"
        title="Attacker Commands"
        summary={`${uniqueCommandCount} Unique`}
      >
        <div className="flex flex-col h-[300px]">
          <div className="flex gap-2 items-center mb-3">
            <CustomDropdown
              options={[{ label: "Most Used", value: "most" }, { label: "Least Used", value: "least" }]}
              value={commandMode}
              onChange={(val) => onCommandModeChange(val as "most" | "least")}
              className="w-28 shrink-0"
            />
            <input
              type="text"
              value={commandSearch}
              onChange={(e) => onCommandSearchChange(e.target.value)}
              placeholder="Search..."
              className="w-full bg-white dark:bg-[#0f0f0f] border border-slate-200 dark:border-white/10 rounded px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
          <div className="flex-1 overflow-y-auto border border-slate-100 dark:border-white/5 rounded-md">
            <table className="w-full text-left">
              <thead className="bg-slate-50 dark:bg-white/5 text-[10px] text-slate-500 sticky top-0 backdrop-blur-md">
                <tr>
                  <th className="px-4 py-2 font-medium w-12">No.</th>
                  <th className="px-4 py-2 font-medium">Command</th>
                  <th className="px-4 py-2 font-medium w-16 text-right">Freq</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-white/5 text-xs">
                {pagedCommands.length === 0 ? (
                  <tr><td className="px-4 py-3 text-slate-500 text-center" colSpan={3}>No commands yet.</td></tr>
                ) : pagedCommands.map((item, index) => (
                  <tr className="hover:bg-slate-50 dark:hover:bg-white/5" key={`${commandMode}-${item.command}`}>
                    <td className="px-4 py-2 text-slate-400 font-mono">{(commandCurrentPage - 1) * pageSize + index + 1}</td>
                    <td className="px-4 py-2 text-slate-700 dark:text-slate-300 font-mono break-all leading-tight">{item.command}</td>
                    <td className="px-4 py-2 text-slate-500 font-mono text-right">{item.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-3 flex items-center justify-between">
            <span className="text-[10px] text-slate-500">Page {commandCurrentPage} of {commandTotalPages}</span>
            <div className="flex gap-1">
              {pageNumbers.map((page) => (
                <button
                  key={page}
                  onClick={() => onCommandPageChange(page)}
                  className={`w-5 h-5 rounded text-[10px] font-medium ${page === commandCurrentPage ? "bg-blue-600 text-white" : "bg-white dark:bg-[#0f0f0f] border border-slate-200 dark:border-white/10 text-slate-500"}`}
                >
                  {page}
                </button>
              ))}
            </div>
          </div>
        </div>
      </CollapsiblePanel>

      <CollapsiblePanel
        expanded={passwordsExpanded}
        onToggle={onTogglePasswords}
        icon={ShieldAlert}
        iconColor="text-fuchsia-500"
        title="Password Word Cloud"
        summary={`${passwordWords.length} Tokens`}
      >
        <div className="h-[300px] overflow-y-auto border border-slate-100 dark:border-white/5 rounded-md p-3">
          {passwordWords.length === 0 ? (
            <div className="text-xs text-slate-500 text-center h-full flex items-center justify-center">
              No captured password words in selected window.
            </div>
          ) : (
            <div className="flex flex-wrap gap-2 items-center">
              {passwordWords.map((item) => {
                const scale = item.count / maxPasswordCount;
                const fontSize = Math.round(12 + scale * 20);
                const opacity = 0.55 + scale * 0.45;
                return (
                  <span
                    key={item.word}
                    title={`${item.word} (${item.count})`}
                    className="font-mono leading-none px-2 py-1 rounded border border-fuchsia-500/20 bg-fuchsia-500/10 text-fuchsia-700 dark:text-fuchsia-300"
                    style={{ fontSize: `${fontSize}px`, opacity }}
                  >
                    {item.word}
                  </span>
                );
              })}
            </div>
          )}
        </div>
      </CollapsiblePanel>
    </div>
  );
}
