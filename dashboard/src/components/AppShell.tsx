"use client";

import type { ReactNode } from "react";
import Sidebar from "@/components/Sidebar";
import AIChatAgent from "@/components/AIChatAgent";

export default function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden flex-col bg-slate-50 text-slate-900 antialiased selection:bg-blue-500/30 transition-colors duration-300 dark:bg-[#050505] dark:text-slate-100 md:flex-row">
      <Sidebar />
      <main className="flex-1 min-w-0 h-full overflow-y-auto bg-slate-50 p-4 dark:bg-[#050505] md:p-6 lg:p-8">
        {children}
      </main>
      <AIChatAgent />
    </div>
  );
}
