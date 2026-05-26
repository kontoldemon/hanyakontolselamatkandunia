"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { Lock, ShieldCheck } from "lucide-react";

function safeNextPath(value: string | null) {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.includes("://")) {
    return "/";
  }
  return value === "/signin" ? "/" : value;
}

export default function SignInPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");

    const response = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });

    setLoading(false);
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      setError(data.error || "Sign in failed");
      return;
    }

    const nextPath = new URLSearchParams(window.location.search).get("next");
    router.replace(safeNextPath(nextPath));
    router.refresh();
  }

  return (
    <main className="min-h-screen bg-slate-50 dark:bg-[#050505] text-slate-900 dark:text-slate-100 flex items-center justify-center p-4">
      <form
        onSubmit={submit}
        className="w-full max-w-sm rounded-xl border border-slate-200 dark:border-white/10 bg-white dark:bg-[#0a0a0a] p-6 shadow-sm"
      >
        <div className="flex items-center gap-3 mb-6">
          <div className="p-2 rounded-lg bg-blue-600 text-white">
            <ShieldCheck size={22} />
          </div>
          <div>
            <h1 className="font-bold text-lg">CloudSentinel</h1>
            <p className="text-xs text-slate-500 dark:text-slate-400">Dashboard access</p>
          </div>
        </div>

        <label className="block text-sm font-medium mb-2">Username</label>
        <input
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          autoComplete="username"
          className="w-full rounded-lg border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 px-3 py-2.5 text-sm mb-4"
          required
        />

        <label className="block text-sm font-medium mb-2">Password</label>
        <input
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          autoComplete="current-password"
          type="password"
          className="w-full rounded-lg border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 px-3 py-2.5 text-sm"
          required
        />

        {error && (
          <p className="mt-3 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-sm text-red-500">
            {error}
          </p>
        )}

        <button
          disabled={loading}
          className="mt-5 w-full inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-500 disabled:opacity-60 transition-colors"
        >
          <Lock size={16} />
          {loading ? "Signing in" : "Sign in"}
        </button>
      </form>
    </main>
  );
}
