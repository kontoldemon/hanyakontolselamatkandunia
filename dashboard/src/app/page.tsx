import Link from "next/link";
import {
  ArrowRight, Shield, Globe, Activity, Lock,
  Crosshair, Terminal, Brain, Fingerprint, Cpu, Zap,
  ChevronRight, ShieldCheck, Server, Database, MonitorDot,
} from "lucide-react";
import type { Metadata } from "next";
import HeroGlobe from "@/components/HeroGlobe";

export const metadata: Metadata = {
  title: "CloudSentinel | Enterprise SSH Threat Detection System",
  description: "Advanced honeypot and threat intelligence dashboard for real-time SSH attack analysis, monitoring, and active defense.",
  keywords: ["SSH", "Honeypot", "Threat Intelligence", "Cybersecurity", "Dashboard", "Active Defense", "MITRE ATT&CK"],
  openGraph: {
    title: "CloudSentinel - Active Threat Defense",
    description: "Enterprise SSH Threat Detection System mapping attacks to the MITRE ATT&CK framework.",
    url: "https://cloudsentinel.zis3c.dev",
    siteName: "CloudSentinel",
    locale: "en_US",
    type: "website",
  },
};

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[#050505] text-slate-100 flex flex-col selection:bg-blue-500/30 font-sans overflow-x-hidden">

      {/* ── Navbar ─────────────────────────────────────────────────────────── */}
      <nav className="flex items-center justify-between p-5 md:px-12 border-b border-white/5 bg-[#0a0a0a]/70 backdrop-blur-xl sticky top-0 z-50">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-blue-600 text-white shadow-lg shadow-blue-500/20">
            <Shield size={22} />
          </div>
          <span className="font-bold text-lg tracking-tight">CloudSentinel</span>
        </div>
        <div className="hidden md:flex items-center gap-8 text-sm text-slate-400">
          <a href="#features" className="hover:text-white transition-colors">Features</a>
          <a href="#how-it-works" className="hover:text-white transition-colors">How It Works</a>
          <a href="#architecture" className="hover:text-white transition-colors">Architecture</a>
        </div>
        <Link
          href="/signin"
          className="group flex items-center gap-2 px-5 py-2.5 rounded-full bg-white text-slate-900 font-semibold text-sm hover:scale-105 transition-all shadow-md"
        >
          Dashboard Login
          <ArrowRight size={16} className="group-hover:translate-x-1 transition-transform" />
        </Link>
      </nav>

      {/* ── Hero + Globe ───────────────────────────────────────────────────── */}
      <section className="relative min-h-[90vh] flex items-center justify-center overflow-hidden">
        {/* Globe Canvas */}
        <HeroGlobe />
        {/* Radial gradient overlay for readability */}
        <div className="absolute inset-0 z-[1] bg-gradient-to-b from-[#050505]/40 via-transparent to-[#050505]" />
        <div className="absolute inset-0 z-[1] bg-gradient-to-r from-[#050505]/60 via-transparent to-[#050505]/60" />

        {/* Hero content */}
        <div className="relative z-10 text-center max-w-4xl px-6 space-y-6">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-blue-500/20 bg-blue-500/10 text-blue-400 text-xs font-semibold uppercase tracking-widest">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 bg-blue-400" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500" />
            </span>
            System Active — Real-Time Monitoring
          </div>

          <h1 className="text-5xl md:text-7xl font-extrabold tracking-tighter leading-[1.1]">
            Enterprise Grade <br className="hidden md:block" />
            <span className="bg-gradient-to-r from-blue-400 via-cyan-400 to-indigo-400 bg-clip-text text-transparent">
              Threat Intelligence
            </span>
          </h1>

          <p className="text-lg md:text-xl text-slate-400 max-w-2xl mx-auto leading-relaxed">
            Monitor, analyze, and neutralize SSH-based attacks in real-time. CloudSentinel maps adversary behaviors to the
            MITRE ATT&CK framework with an interactive war room dashboard powered by AI.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-4">
            <Link
              href="/signin"
              className="w-full sm:w-auto px-8 py-4 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-bold shadow-lg shadow-blue-500/25 hover:shadow-blue-500/40 hover:-translate-y-1 transition-all flex items-center justify-center gap-2"
            >
              <Lock size={18} />
              Access Dashboard
            </Link>
            <a
              href="#features"
              className="w-full sm:w-auto px-8 py-4 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 text-white font-semibold text-sm flex items-center justify-center gap-2 transition-all"
            >
              Explore Features
              <ChevronRight size={16} />
            </a>
          </div>
        </div>

        {/* Bottom fade */}
        <div className="absolute bottom-0 left-0 right-0 h-32 bg-gradient-to-t from-[#050505] to-transparent z-[2]" />
      </section>

      {/* ── Stats Banner ───────────────────────────────────────────────────── */}
      <section className="relative z-10 -mt-16 px-6 md:px-12">
        <div className="max-w-6xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-4 md:gap-6">
          <StatCard value="50,000+" label="Threats Analyzed" icon={<Crosshair size={20} className="text-red-400" />} />
          <StatCard value="190+" label="Countries Tracked" icon={<Globe size={20} className="text-blue-400" />} />
          <StatCard value="<15ms" label="Avg MTTB" icon={<Zap size={20} className="text-amber-400" />} />
          <StatCard value="24/7" label="Active Monitoring" icon={<Activity size={20} className="text-emerald-400" />} />
        </div>
      </section>

      {/* ── How It Works ───────────────────────────────────────────────────── */}
      <section id="how-it-works" className="py-24 px-6 md:px-12">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <p className="text-xs font-semibold uppercase tracking-widest text-blue-400 mb-3">How It Works</p>
            <h2 className="text-3xl md:text-4xl font-extrabold tracking-tight">
              Three-Stage Active Defense Pipeline
            </h2>
            <p className="text-slate-400 mt-4 max-w-2xl mx-auto">
              CloudSentinel operates as a layered defense system that captures, analyzes, and responds to SSH-based threats autonomously.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <PipelineStep
              step="01"
              color="text-cyan-400"
              borderColor="border-cyan-500/20"
              bgColor="bg-cyan-500/5"
              icon={<Crosshair size={28} />}
              title="Detect"
              description="A production-grade Cowrie SSH honeypot captures attacker sessions, credentials, commands, and SSH client fingerprints (HASSH) in real-time. Every keystroke is recorded."
            />
            <PipelineStep
              step="02"
              color="text-blue-400"
              borderColor="border-blue-500/20"
              bgColor="bg-blue-500/5"
              icon={<Brain size={28} />}
              title="Analyze"
              description="Captured data is streamed to ClickHouse for high-speed analytics. Each session is automatically mapped to MITRE ATT&CK techniques and fed to an AI-powered analysis engine."
            />
            <PipelineStep
              step="03"
              color="text-indigo-400"
              borderColor="border-indigo-500/20"
              bgColor="bg-indigo-500/5"
              icon={<ShieldCheck size={28} />}
              title="Neutralize"
              description="The SOAR engine automatically triggers iptables firewall blocks, publishes threat intelligence events, and can execute active defense playbooks — all within milliseconds."
            />
          </div>
        </div>
      </section>

      {/* ── Feature Deep-Dive ──────────────────────────────────────────────── */}
      <section id="features" className="py-24 px-6 md:px-12 bg-[#0a0a0a]/50">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <p className="text-xs font-semibold uppercase tracking-widest text-blue-400 mb-3">Capabilities</p>
            <h2 className="text-3xl md:text-4xl font-extrabold tracking-tight">
              Built for Security Operations
            </h2>
            <p className="text-slate-400 mt-4 max-w-2xl mx-auto">
              Every component is designed for real-world threat hunting and incident response workflows.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <FeatureCard
              icon={<Globe className="text-blue-400" size={24} />}
              title="Global Threat Map"
              description="Interactive D3.js world map with real-time attack line animations. Click any country to filter by region. Attack origins are geo-located with IP-to-ASN resolution."
              tags={["D3.js", "GeoIP", "Real-Time"]}
            />
            <FeatureCard
              icon={<Terminal className="text-emerald-400" size={24} />}
              title="Live Session Replay"
              description="Watch attacker commands execute in a terminal emulator. See both attacker input and honeypot responses timestamped to the millisecond."
              tags={["WebSocket", "Terminal", "Replay"]}
            />
            <FeatureCard
              icon={<Brain className="text-purple-400" size={24} />}
              title="MITRE ATT&CK Mapping"
              description="Automated technique classification maps each session to the MITRE framework. Identify initial access, execution, persistence, and exfiltration patterns."
              tags={["MITRE", "Classification", "TTP"]}
            />
            <FeatureCard
              icon={<Shield className="text-red-400" size={24} />}
              title="SOAR Automated Response"
              description="Security Orchestration triggers iptables blocks within milliseconds of detection. Mean Time To Block (MTTB) averages under 15ms across all sensors."
              tags={["SOAR", "iptables", "Automation"]}
            />
            <FeatureCard
              icon={<Fingerprint className="text-amber-400" size={24} />}
              title="HASSH Fingerprinting"
              description="Unique SSH client fingerprinting identifies attacker toolkits before credentials are even attempted. Track tool evolution across campaigns."
              tags={["HASSH", "Fingerprint", "Tracking"]}
            />
            <FeatureCard
              icon={<Cpu className="text-cyan-400" size={24} />}
              title="AI-Powered Analysis"
              description="Built-in AI assistant explains attacker behavior, suggests MITRE mappings, navigates the dashboard, and can execute defensive actions on your command."
              tags={["GPT-4o", "NLP", "Agent"]}
            />
          </div>
        </div>
      </section>

      {/* ── Architecture ───────────────────────────────────────────────────── */}
      <section id="architecture" className="py-24 px-6 md:px-12">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <p className="text-xs font-semibold uppercase tracking-widest text-blue-400 mb-3">System Architecture</p>
            <h2 className="text-3xl md:text-4xl font-extrabold tracking-tight">
              Cloud-Native Defense Stack
            </h2>
            <p className="text-slate-400 mt-4 max-w-2xl mx-auto">
              A horizontally scalable architecture designed for production deployment across multiple cloud regions.
            </p>
          </div>

          <div className="relative">
            {/* Pipeline flow */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
              <ArchNode
                icon={<Server size={28} />}
                label="SSH Honeypot"
                tech="Cowrie"
                description="Captures attacker sessions, credentials, and TTY data on DigitalOcean"
                color="text-cyan-400"
                borderColor="border-cyan-500/20"
              />
              <ArchNode
                icon={<Database size={28} />}
                label="Analytics Engine"
                tech="ClickHouse"
                description="High-speed columnar storage for real-time query and aggregation"
                color="text-amber-400"
                borderColor="border-amber-500/20"
              />
              <ArchNode
                icon={<MonitorDot size={28} />}
                label="Dashboard"
                tech="Next.js + Socket.io"
                description="War Room UI with live WebSocket telemetry and AI-powered chat"
                color="text-blue-400"
                borderColor="border-blue-500/20"
              />
              <ArchNode
                icon={<ShieldCheck size={28} />}
                label="SOAR Engine"
                tech="Python + iptables"
                description="Automated blocking, threat intel publishing, and active playbooks"
                color="text-red-400"
                borderColor="border-red-500/20"
              />
            </div>
            {/* Connection lines (desktop only) */}
            <div className="hidden md:block absolute top-1/2 left-[25%] right-[25%] h-px bg-gradient-to-r from-cyan-500/30 via-amber-500/30 to-blue-500/30 -translate-y-1/2 z-0" />
          </div>
        </div>
      </section>

      {/* ── CTA ────────────────────────────────────────────────────────────── */}
      <section className="py-24 px-6 md:px-12">
        <div className="max-w-4xl mx-auto text-center">
          <div className="rounded-2xl border border-white/10 bg-gradient-to-br from-blue-600/10 via-[#0a0a0a] to-indigo-600/10 p-12 md:p-16 relative overflow-hidden">
            {/* Glow accents */}
            <div className="absolute -top-24 -right-24 w-48 h-48 bg-blue-500/20 rounded-full blur-3xl" />
            <div className="absolute -bottom-24 -left-24 w-48 h-48 bg-indigo-500/20 rounded-full blur-3xl" />

            <div className="relative z-10">
              <h2 className="text-3xl md:text-4xl font-extrabold tracking-tight mb-4">
                Ready to See Your Threats?
              </h2>
              <p className="text-slate-400 max-w-xl mx-auto mb-8">
                Access the CloudSentinel War Room to monitor live attacks, replay attacker sessions, and take automated defensive action — all from a single dashboard.
              </p>
              <Link
                href="/signin"
                className="inline-flex items-center gap-2 px-8 py-4 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-bold shadow-lg shadow-blue-500/25 hover:shadow-blue-500/40 hover:-translate-y-1 transition-all"
              >
                <Lock size={18} />
                Enter War Room
                <ArrowRight size={18} />
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* ── Footer ─────────────────────────────────────────────────────────── */}
      <footer className="border-t border-white/5 py-10 text-center text-sm text-slate-500">
        <div className="max-w-6xl mx-auto px-6 flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-md bg-blue-600 text-white">
              <Shield size={14} />
            </div>
            <span className="font-semibold text-slate-400">CloudSentinel</span>
          </div>
          <p>&copy; {new Date().getFullYear()} CloudSentinel Threat Detection System. All rights reserved.</p>
          <div className="flex gap-4 text-slate-500 text-xs">
            <span>FYP Project</span>
            <span>•</span>
            <span>MITRE ATT&CK</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

// ─── Sub-Components ──────────────────────────────────────────────────────────

function StatCard({ value, label, icon }: { value: string; label: string; icon: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-white/5 bg-[#0a0a0a]/80 backdrop-blur-xl p-5 text-center shadow-lg">
      <div className="flex justify-center mb-2">{icon}</div>
      <div className="text-2xl md:text-3xl font-extrabold tracking-tight text-white">{value}</div>
      <div className="text-xs text-slate-400 font-medium mt-1">{label}</div>
    </div>
  );
}

function PipelineStep({ step, color, borderColor, bgColor, icon, title, description }: {
  step: string; color: string; borderColor: string; bgColor: string; icon: React.ReactNode; title: string; description: string;
}) {
  return (
    <div className={`relative rounded-2xl border ${borderColor} ${bgColor} p-8 transition-all hover:scale-[1.02]`}>
      <div className={`text-[10px] font-bold uppercase tracking-widest ${color} mb-4`}>Step {step}</div>
      <div className={`p-3 rounded-xl border ${borderColor} bg-[#050505] w-fit mb-5 ${color}`}>
        {icon}
      </div>
      <h3 className="text-xl font-bold mb-3">{title}</h3>
      <p className="text-sm text-slate-400 leading-relaxed">{description}</p>
    </div>
  );
}

function FeatureCard({ icon, title, description, tags }: {
  icon: React.ReactNode; title: string; description: string; tags: string[];
}) {
  return (
    <div className="group flex flex-col p-6 rounded-2xl border border-white/5 bg-white/[0.02] hover:bg-white/[0.05] hover:border-white/10 transition-all">
      <div className="p-3 rounded-xl bg-[#050505] border border-white/10 mb-5 w-fit group-hover:scale-110 transition-transform">
        {icon}
      </div>
      <h3 className="text-lg font-bold mb-2">{title}</h3>
      <p className="text-sm text-slate-400 leading-relaxed flex-1">{description}</p>
      <div className="flex flex-wrap gap-2 mt-4">
        {tags.map((tag) => (
          <span key={tag} className="text-[10px] font-semibold uppercase tracking-wider px-2 py-1 rounded-md bg-white/5 text-slate-500 border border-white/5">
            {tag}
          </span>
        ))}
      </div>
    </div>
  );
}

function ArchNode({ icon, label, tech, description, color, borderColor }: {
  icon: React.ReactNode; label: string; tech: string; description: string; color: string; borderColor: string;
}) {
  return (
    <div className={`relative z-10 rounded-2xl border ${borderColor} bg-[#0a0a0a] p-6 text-center transition-all hover:scale-105`}>
      <div className={`${color} flex justify-center mb-3`}>{icon}</div>
      <h4 className="font-bold text-sm mb-1">{label}</h4>
      <div className={`text-[10px] font-semibold uppercase tracking-widest ${color} mb-3`}>{tech}</div>
      <p className="text-xs text-slate-500 leading-relaxed">{description}</p>
    </div>
  );
}
