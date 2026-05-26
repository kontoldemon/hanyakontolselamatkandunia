"use client";

import type { ReactNode } from "react";
import { usePathname } from "next/navigation";
import Sidebar from "@/components/Sidebar";

const shelllessPaths = new Set(["/signin", "/offline", "/505"]);

export default function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  if (shelllessPaths.has(pathname)) {
    return (
      <div className="min-h-screen bg-slate-50 text-slate-900 antialiased selection:bg-blue-500/30 dark:bg-[#050505] dark:text-slate-100">
        {children}
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-900 antialiased selection:bg-blue-500/30 transition-colors duration-300 dark:bg-[#050505] dark:text-slate-100 md:flex-row">
      <Sidebar />
      <main className="flex-1 min-w-0 bg-slate-50 p-4 dark:bg-[#050505] md:p-6 xl:p-8">
        {children}
      </main>
    </div>
  );
}
