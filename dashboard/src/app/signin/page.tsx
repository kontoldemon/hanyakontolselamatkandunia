"use client";

import Image from "next/image";
import Link from "next/link";
import { FormEvent, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, CheckCircle2, Eye, EyeOff, Lock } from "lucide-react";
import { Turnstile } from "@marsidev/react-turnstile";

function safeNextPath(value: string | null) {
  if (!value) {
    return "/dashboard";
  }
  const base = "https://cloudsentinel.invalid";
  try {
    const target = new URL(value, base);
    if (target.origin !== base) {
      return "/dashboard";
    }
    const path = `${target.pathname}${target.search}${target.hash}`;
    return path === "/signin" ? "/dashboard" : path;
  } catch {
    return "/dashboard";
  }
}

export default function SignInPage() {
  const router = useRouter();
  const [step, setStep] = useState<"login" | "otp" | "success">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [turnstileToken, setTurnstileToken] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const [otp, setOtp] = useState(["", "", "", "", "", ""]);
  const otpRefs = useRef<(HTMLInputElement | null)[]>([]);

  async function handleLoginSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!turnstileToken) {
      setError("Please complete the verification check.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password, turnstileToken }),
      });
      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        setError(data.error || "Sign in failed");
        return;
      }

      if (data.requireOtp) {
        setStep("otp");
        setTimeout(() => otpRefs.current[0]?.focus(), 100);
      } else {
        finishLogin();
      }
    } catch {
      setError("Unable to reach the server. Check your connection and try again.");
    } finally {
      setLoading(false);
    }
  }

  async function handleOtpSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const otpString = otp.join("");
    if (otpString.length !== 6) {
      setError("Please enter the 6-digit code.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const response = await fetch("/api/auth/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, otp: otpString }),
      });
      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        setError(data.error || "Verification failed");
        return;
      }

      setStep("success");
      setTimeout(finishLogin, 1200);
    } catch {
      setError("Unable to reach the server. Check your connection and try again.");
    } finally {
      setLoading(false);
    }
  }

  function finishLogin() {
    const nextPath = new URLSearchParams(window.location.search).get("next");
    router.replace(safeNextPath(nextPath));
    router.refresh();
  }

  const handleOtpChange = (index: number, value: string) => {
    if (value.length > 1) value = value.slice(-1);
    if (!/^\d*$/.test(value)) return;

    const newOtp = [...otp];
    newOtp[index] = value;
    setOtp(newOtp);

    if (value && index < 5) {
      otpRefs.current[index + 1]?.focus();
    }
  };

  const handleOtpKeyDown = (index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Backspace" && !otp[index] && index > 0) {
      otpRefs.current[index - 1]?.focus();
    }
  };

  const handlePaste = (e: React.ClipboardEvent) => {
    e.preventDefault();
    const pastedData = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6);
    if (pastedData) {
      const newOtp = [...otp];
      for (let i = 0; i < pastedData.length; i++) {
        newOtp[i] = pastedData[i];
      }
      setOtp(newOtp);
      const nextIndex = Math.min(pastedData.length, 5);
      otpRefs.current[nextIndex]?.focus();
    }
  };

  return (
    <main className="relative flex min-h-dvh items-center justify-center overflow-hidden bg-slate-50 px-4 py-8 text-slate-900 antialiased dark:bg-[#050505] dark:text-slate-100">
      {/* Ambient Radial Lighting & Subtle Grid Background */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 overflow-hidden"
      >
        <div className="absolute top-1/2 left-1/2 h-[580px] w-[580px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-blue-500/20 blur-[130px] dark:bg-blue-500/25" />
        <div className="absolute top-1/3 left-1/2 h-[380px] w-[380px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-indigo-500/15 blur-[110px] dark:bg-indigo-500/20" />
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#8080800a_1px,transparent_1px),linear-gradient(to_bottom,#8080800a_1px,transparent_1px)] bg-[size:24px_24px] [mask-image:radial-gradient(ellipse_65%_55%_at_50%_50%,#000_60%,transparent_100%)]" />
      </div>

      <div className="relative w-full max-w-[370px]">
        {/* Back Link */}
        <div className="mb-4">
          <Link
            href="/"
            className="inline-flex min-h-9 items-center gap-1.5 rounded-full border border-slate-200/80 bg-white/70 px-3 py-1 text-xs font-medium text-slate-500 shadow-sm backdrop-blur-md transition hover:border-slate-300 hover:text-slate-900 dark:border-white/10 dark:bg-[#0a0a0c]/70 dark:text-slate-400 dark:hover:border-white/20 dark:hover:text-white"
          >
            <ArrowLeft size={13} />
            <span>Back to Home</span>
          </Link>
        </div>

        {/* Compact Glass Card */}
        <div className="overflow-hidden rounded-3xl border border-slate-200/80 bg-white/80 p-6 shadow-xl backdrop-blur-xl transition-all duration-300 sm:p-7 dark:border-white/10 dark:bg-[#0a0a0c]/85 dark:shadow-[0_20px_50px_rgba(0,0,0,0.6)]">
          {/* Header with Tab Logo */}
          <div className="mb-5 flex flex-col items-center text-center">
            <div className="mb-2 flex h-8 w-8 items-center justify-center rounded-xl border border-blue-500/20 bg-blue-500/10 shadow-sm">
              <Image
                src="/logo.svg"
                alt="CloudSentinel"
                width={18}
                height={18}
                className="h-[18px] w-[18px]"
              />
            </div>
            <h1 className="font-display text-base font-bold tracking-tight text-slate-900 sm:text-lg dark:text-white">
              Cloud<span className="text-blue-600 dark:text-blue-400">Sentinel</span>
            </h1>
            <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
              {step === "login"
                ? "Sign in to access the War Room"
                : step === "otp"
                  ? "Enter two-factor security code"
                  : "Identity verified"}
            </p>
          </div>

          {error && (
            <div className="mb-4 rounded-xl border border-red-500/20 bg-red-500/10 px-3 py-2 text-xs text-red-500">
              {error}
            </div>
          )}

          {/* LOGIN FORM */}
          {step === "login" && (
            <form onSubmit={handleLoginSubmit} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-slate-700 dark:text-slate-300">
                  Username
                </label>
                <input
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  autoComplete="username"
                  placeholder="Username"
                  className="input-minimal mt-1 h-11 w-full rounded-xl bg-slate-50/80 px-3 text-xs text-slate-900 transition placeholder:font-normal placeholder:text-slate-400 sm:h-9.5 dark:bg-white/[0.04] dark:text-white dark:placeholder:text-slate-500"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 dark:text-slate-300">
                  Password
                </label>
                <div className="relative mt-1">
                  <input
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    autoComplete="current-password"
                    type={showPassword ? "text" : "password"}
                    placeholder="Password"
                    className="input-minimal h-11 w-full rounded-xl bg-slate-50/80 px-3 pr-11 text-xs text-slate-900 transition placeholder:font-normal placeholder:text-slate-400 sm:h-9.5 dark:bg-white/[0.04] dark:text-white dark:placeholder:text-slate-500"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute top-1/2 right-0.5 flex h-10 w-10 -translate-y-1/2 items-center justify-center text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
                    aria-label={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? <EyeOff size={14} /> : <Eye size={14} />}
                  </button>
                </div>
              </div>

              {/* Turnstile Security Check */}
              <div className="pt-1.5 flex justify-center max-w-full overflow-x-auto">
                <Turnstile
                  siteKey={process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY || "1x00000000000000000000AA"}
                  onSuccess={(token) => setTurnstileToken(token)}
                  options={{ theme: "auto", size: "normal" }}
                />
              </div>

              <button
                disabled={loading || !turnstileToken}
                className="mt-3 inline-flex h-11 w-full items-center justify-center gap-1.5 rounded-full bg-blue-600 px-4 text-xs font-semibold text-white shadow-md shadow-blue-500/20 transition hover:bg-blue-500 active:scale-95 disabled:cursor-not-allowed disabled:opacity-50 sm:h-9.5"
              >
                <Lock size={12} />
                <span>{loading ? "Authenticating..." : "Sign In"}</span>
              </button>
            </form>
          )}

          {/* OTP STEP */}
          {step === "otp" && (
            <form onSubmit={handleOtpSubmit} className="space-y-4">
              <div className="text-center">
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Enter the 6-digit code sent to your registered authentication method.
                </p>
              </div>

              <div className="flex justify-center gap-1.5 sm:gap-2">
                {otp.map((digit, index) => (
                  <input
                    key={index}
                    ref={(el) => {
                      otpRefs.current[index] = el;
                    }}
                    type="text"
                    inputMode="numeric"
                    value={digit}
                    onChange={(e) => handleOtpChange(index, e.target.value)}
                    onKeyDown={(e) => handleOtpKeyDown(index, e)}
                    onPaste={handlePaste}
                    className="h-11 w-9 sm:w-10 rounded-xl border border-slate-200 bg-slate-50 text-center font-mono text-base font-bold text-slate-900 transition outline-none focus:border-blue-500 focus:bg-white focus:outline-none focus-visible:outline-none dark:border-white/10 dark:bg-white/[0.04] dark:text-white dark:focus:border-blue-500 dark:focus:bg-white/[0.08]"
                    maxLength={1}
                  />
                ))}
              </div>

              <button
                disabled={loading || otp.join("").length !== 6}
                className="inline-flex h-11 w-full items-center justify-center gap-1.5 rounded-full bg-blue-600 px-4 text-xs font-semibold text-white shadow-md shadow-blue-500/20 transition hover:bg-blue-500 active:scale-95 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading ? "Verifying..." : "Verify Code"}
              </button>

              <button
                type="button"
                onClick={() => setStep("login")}
                className="w-full text-center text-xs text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-white"
              >
                Back to sign in
              </button>
            </form>
          )}

          {/* SUCCESS STEP */}
          {step === "success" && (
            <div className="flex flex-col items-center justify-center py-3 text-center animate-in fade-in zoom-in-95 duration-200">
              <div className="mb-3.5 -mt-1 flex h-12 w-12 items-center justify-center rounded-full border border-emerald-500/20 bg-emerald-500/10 text-emerald-500 shadow-sm shadow-emerald-500/10">
                <CheckCircle2 size={24} className="-translate-y-[1.5px]" />
              </div>
              <h2 className="font-display text-base font-bold text-slate-900 dark:text-white">
                Access Granted
              </h2>
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                Opening War Room dashboard...
              </p>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
