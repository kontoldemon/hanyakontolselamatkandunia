import Link from "next/link";
import { ArrowRight, Shield, Globe, Activity, Lock } from "lucide-react";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "CloudSentinel | Enterprise SSH Threat Detection System",
  description: "Advanced honeypot and threat intelligence dashboard for real-time SSH attack analysis, monitoring, and active defense.",
  keywords: ["SSH", "Honeypot", "Threat Intelligence", "Cybersecurity", "Dashboard", "Active Defense", "MITRE ATT&CK"],
  openGraph: {
    title: "CloudSentinel - Active Threat Defense",
    description: "Enterprise SSH Threat Detection System mapping attacks to the MITRE ATT&CK framework.",
    url: "https://cloudsentinel.dev",
    siteName: "CloudSentinel",
    locale: "en_US",
    type: "website",
  },
};

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-slate-50 dark:bg-[#050505] text-slate-900 dark:text-slate-100 flex flex-col selection:bg-blue-500/30 font-sans">
      <nav className="flex items-center justify-between p-6 md:px-12 border-b border-slate-200 dark:border-white/5 bg-white/50 dark:bg-[#0a0a0a]/50 backdrop-blur-xl sticky top-0 z-50">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-blue-600 text-white shadow-lg shadow-blue-500/20">
            <Shield size={24} />
          </div>
          <span className="font-bold text-xl tracking-tight">CloudSentinel</span>
        </div>
        <div>
          <Link
            href="/signin"
            className="group flex items-center gap-2 px-5 py-2.5 rounded-full bg-slate-900 dark:bg-white text-white dark:text-slate-900 font-semibold text-sm hover:scale-105 transition-all shadow-md"
          >
            Dashboard Login
            <ArrowRight size={16} className="group-hover:translate-x-1 transition-transform" />
          </Link>
        </div>
      </nav>

      <main className="flex-1 flex flex-col items-center justify-center text-center p-6 mt-16 md:mt-24">
        <div className="max-w-4xl space-y-8 animate-in fade-in slide-in-from-bottom-8 duration-1000">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-blue-500/20 bg-blue-500/10 text-blue-600 dark:text-blue-400 text-xs font-semibold uppercase tracking-widest mb-4">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 bg-blue-400"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500"></span>
            </span>
            System Online
          </div>
          
          <h1 className="text-5xl md:text-7xl font-extrabold tracking-tighter leading-tight">
            Enterprise Grade <br className="hidden md:block" />
            <span className="bg-gradient-to-r from-blue-600 to-indigo-500 bg-clip-text text-transparent">
              Threat Intelligence
            </span>
          </h1>
          
          <p className="text-lg md:text-xl text-slate-600 dark:text-slate-400 max-w-2xl mx-auto leading-relaxed">
            Monitor, analyze, and neutralize SSH-based attacks in real-time. CloudSentinel maps adversary behaviors to the MITRE ATT&CK framework with an interactive war room dashboard.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-8">
            <Link
              href="/signin"
              className="w-full sm:w-auto px-8 py-4 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-bold shadow-lg shadow-blue-500/25 hover:shadow-blue-500/40 hover:-translate-y-1 transition-all flex items-center justify-center gap-2"
            >
              <Lock size={18} />
              Access Dashboard
            </Link>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl w-full mt-32 mb-20">
          <FeatureCard 
            icon={<Globe className="text-blue-500" size={24} />}
            title="Global Threat Map"
            description="Visualize incoming attacks geographically in real-time with granular IP tracking."
          />
          <FeatureCard 
            icon={<Activity className="text-emerald-500" size={24} />}
            title="Live Session Analytics"
            description="Monitor live SSH sessions, executed commands, and automated attacker behaviors."
          />
          <FeatureCard 
            icon={<Shield className="text-indigo-500" size={24} />}
            title="Active Defense"
            description="Automated SOAR integration to instantly block malicious IPs across firewalls."
          />
        </div>
      </main>

      <footer className="border-t border-slate-200 dark:border-white/5 py-8 text-center text-sm text-slate-500 dark:text-slate-400">
        <p>&copy; {new Date().getFullYear()} CloudSentinel Threat Detection System. All rights reserved.</p>
      </footer>
    </div>
  );
}

function FeatureCard({ icon, title, description }: { icon: React.ReactNode, title: string, description: string }) {
  return (
    <div className="flex flex-col items-center text-center p-8 rounded-2xl border border-slate-200 dark:border-white/5 bg-white/50 dark:bg-white/[0.02] hover:bg-white dark:hover:bg-white/[0.04] transition-colors shadow-sm">
      <div className="p-4 rounded-xl bg-slate-50 dark:bg-black border border-slate-100 dark:border-white/10 mb-6 shadow-inner">
        {icon}
      </div>
      <h3 className="text-lg font-bold mb-2">{title}</h3>
      <p className="text-sm text-slate-600 dark:text-slate-400 leading-relaxed">{description}</p>
    </div>
  );
}
