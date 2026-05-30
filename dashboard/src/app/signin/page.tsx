"use client";

import { FormEvent, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { Lock, ShieldCheck, Eye, EyeOff, CheckCircle2 } from "lucide-react";
import { Turnstile } from "@marsidev/react-turnstile";

function safeNextPath(value: string | null) {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.includes("://")) {
    return "/dashboard";
  }
  return value === "/signin" ? "/dashboard" : value;
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

  // OTP State
  const [otp, setOtp] = useState(["", "", "", "", "", ""]);
  const otpRefs = useRef<(HTMLInputElement | null)[]>([]);

  async function handleLoginSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!turnstileToken) {
      setError("Please complete the captcha.");
      return;
    }

    setLoading(true);
    setError("");

    const response = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password, turnstileToken }),
    });

    setLoading(false);
    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      setError(data.error || "Sign in failed");
      return;
    }

    if (data.requireOtp) {
      setStep("otp");
      // Focus first OTP input
      setTimeout(() => otpRefs.current[0]?.focus(), 100);
    } else {
      // Fallback if no OTP required
      finishLogin();
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

    const response = await fetch("/api/auth/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, otp: otpString }),
    });

    setLoading(false);
    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      setError(data.error || "Verification failed");
      return;
    }

    setStep("success");
    setTimeout(finishLogin, 1500);
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

    // Auto-advance
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
    <main className="min-h-screen bg-slate-50 dark:bg-[#050505] text-slate-900 dark:text-slate-100 flex items-center justify-center p-4">
      <div className="w-full max-w-md rounded-2xl border border-slate-200 dark:border-white/10 bg-white dark:bg-[#0a0a0a] p-8 shadow-xl shadow-slate-200/50 dark:shadow-black/50 transition-all duration-500 relative overflow-hidden">
        
        {/* Header */}
        <div className="flex items-center gap-4 mb-8">
          <div className="p-3 rounded-xl bg-blue-600 text-white shadow-lg shadow-blue-500/20">
            <ShieldCheck size={28} />
          </div>
          <div>
            <h1 className="font-extrabold text-2xl tracking-tight">CloudSentinel</h1>
            <p className="text-sm text-slate-500 dark:text-slate-400 font-medium">
              {step === "login" ? "Secure Dashboard Access" : step === "otp" ? "Two-Factor Authentication" : "Access Granted"}
            </p>
          </div>
        </div>

        {error && (
          <div className="mb-6 rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-500 animate-in fade-in slide-in-from-top-2">
            {error}
          </div>
        )}

        {/* LOGIN STEP */}
        {step === "login" && (
          <form onSubmit={handleLoginSubmit} className="animate-in fade-in slide-in-from-right-4 duration-300">
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-semibold mb-1.5 text-slate-700 dark:text-slate-300">Username</label>
                <input
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  autoComplete="username"
                  className="w-full rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 px-4 py-3 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-semibold mb-1.5 text-slate-700 dark:text-slate-300">Password</label>
                <div className="relative">
                  <input
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    autoComplete="current-password"
                    type={showPassword ? "text" : "password"}
                    className="w-full rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 px-4 py-3 pr-12 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors p-1"
                  >
                    {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
              </div>

              <div className="pt-3 w-full">
                <p className="text-xs text-slate-500 dark:text-slate-400 mb-2 font-medium">Let us know you&apos;re human</p>
                <div className="w-fit origin-left scale-[0.85] sm:scale-100 transform transition-transform">
                  <Turnstile
                    siteKey={process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY || "1x00000000000000000000AA"}
                    onSuccess={(token) => setTurnstileToken(token)}
                    options={{ theme: 'auto' }}
                  />
                </div>
              </div>
            </div>

            <button
              disabled={loading || !turnstileToken}
              className="mt-8 w-full inline-flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-3.5 text-sm font-bold text-white shadow-lg shadow-blue-500/25 hover:bg-blue-500 hover:shadow-blue-500/40 hover:-translate-y-0.5 disabled:opacity-50 disabled:hover:translate-y-0 disabled:hover:bg-blue-600 transition-all"
            >
              <Lock size={18} />
              {loading ? "Authenticating..." : "Continue"}
            </button>
          </form>
        )}

        {/* OTP STEP */}
        {step === "otp" && (
          <form onSubmit={handleOtpSubmit} className="animate-in fade-in slide-in-from-right-4 duration-300">
            <div className="mb-8 text-center">
              <div className="w-16 h-16 bg-blue-500/10 rounded-full flex items-center justify-center mx-auto mb-4 border border-blue-500/20">
                <ShieldCheck size={32} className="text-blue-500" />
              </div>
              <h2 className="text-xl font-bold mb-2">Check your email</h2>
              <p className="text-sm text-slate-500 dark:text-slate-400 leading-relaxed">
                We&apos;ve sent a 6-digit verification code to your registered email address.
              </p>
            </div>

            <div className="flex gap-2 sm:gap-3 justify-center mb-8">
              {otp.map((digit, index) => (
                <input
                  key={index}
                  ref={(el) => { otpRefs.current[index] = el; }}
                  type="text"
                  inputMode="numeric"
                  value={digit}
                  onChange={(e) => handleOtpChange(index, e.target.value)}
                  onKeyDown={(e) => handleOtpKeyDown(index, e)}
                  onPaste={handlePaste}
                  className="w-10 h-12 sm:w-12 sm:h-14 text-center text-xl font-bold rounded-xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 focus:bg-white dark:focus:bg-white/10 focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none transition-all"
                  maxLength={1}
                />
              ))}
            </div>

            <button
              disabled={loading || otp.join("").length !== 6}
              className="w-full inline-flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-3.5 text-sm font-bold text-white shadow-lg shadow-blue-500/25 hover:bg-blue-500 hover:shadow-blue-500/40 hover:-translate-y-0.5 disabled:opacity-50 disabled:hover:translate-y-0 disabled:hover:bg-blue-600 transition-all"
            >
              {loading ? "Verifying..." : "Verify & Access"}
            </button>
            
            <button
              type="button"
              onClick={() => setStep("login")}
              className="mt-4 w-full text-sm text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 font-medium transition-colors"
            >
              Back to login
            </button>
          </form>
        )}

        {/* SUCCESS STEP */}
        {step === "success" && (
          <div className="py-8 flex flex-col items-center justify-center text-center animate-in fade-in zoom-in-95 duration-500">
            <div className="w-20 h-20 bg-emerald-500/10 rounded-full flex items-center justify-center mb-6 border border-emerald-500/20 relative">
              <div className="absolute inset-0 rounded-full bg-emerald-500/20 animate-ping" />
              <CheckCircle2 size={40} className="text-emerald-500 relative z-10" />
            </div>
            <h2 className="text-2xl font-bold mb-2">Access Granted</h2>
            <p className="text-slate-500 dark:text-slate-400">Redirecting to War Room...</p>
          </div>
        )}
      </div>
    </main>
  );
}
