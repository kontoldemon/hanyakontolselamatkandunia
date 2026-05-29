"use client";

import type { ReactNode } from "react";
import Sidebar from "@/components/Sidebar";
import AIChatAgent from "@/components/AIChatAgent";
import AgentOverlay from "@/components/AgentOverlay";
import { AgentProvider } from "@/lib/AgentContext";

export default function AppShell({ children }: { children: ReactNode }) {
  return (
    <AgentProvider>
      <div className="flex h-screen overflow-hidden flex-col bg-slate-50 text-slate-900 antialiased selection:bg-blue-500/30 transition-colors duration-300 dark:bg-[#050505] dark:text-slate-100 md:flex-row relative z-0">
        <Sidebar />
        <main className="flex-1 min-w-0 h-full overflow-y-auto bg-slate-50 p-4 pb-20 dark:bg-[#050505] md:p-6 md:pb-6 lg:p-8 relative z-0">
          {children}
        </main>
      </div>
      <AIChatAgent />
      <AgentOverlay />
    </AgentProvider>
  );
}
