import Link from "next/link";
import {
  ArrowRight, Shield, Globe, Activity, Lock,
  Crosshair, Terminal, Brain, Fingerprint, Cpu, Zap,
  ChevronRight, ShieldCheck, Server, Database, MonitorDot,
} from "lucide-react";
import type { Metadata } from "next";
import HeroGlobe from "@/components/HeroGlobe";
import LandingAnimations from "@/components/LandingAnimations";

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
    <div className="h-screen w-screen overflow-hidden bg-[#050505] text-slate-100 font-sans selection:bg-blue-500/30 relative">
      {/* Scroll progress bar & intersection tracker */}
      <LandingAnimations />

      {/* ── Fixed Premium Header ───────────────────────────────────────────── */}
      <nav className="fixed top-0 left-0 right-0 h-[56px] flex items-center justify-between px-6 md:px-12 border-b border-white/5 bg-[#050505]/80 backdrop-blur-xl z-50">
        <div className="flex items-center gap-3">
          <div className="p-1.5 rounded-lg bg-blue-600 text-white shadow-lg shadow-blue-500/20">
            <Shield size={18} />
          </div>
          <span className="font-bold text-base tracking-tight text-white">CloudSentinel</span>
        </div>
        <div className="hidden md:flex items-center gap-8 text-sm text-slate-400">
          <a href="#how-it-works" className="hover:text-white transition-colors">How It Works</a>
          <a href="#features" className="hover:text-white transition-colors">Features</a>
          <a href="#architecture" className="hover:text-white transition-colors">Architecture</a>
        </div>
        <Link
          href="/signin"
          className="group flex items-center gap-1.5 px-4 py-1.5 rounded-full bg-white text-slate-900 font-semibold text-xs hover:scale-105 transition-all shadow-md"
        >
          Dashboard Login
          <ArrowRight size={12} className="group-hover:translate-x-0.5 transition-transform" />
        </Link>
      </nav>

      {/* ── Snap Scroll Container ──────────────────────────────────────────── */}
      <div 
        id="snap-container" 
        className="h-full w-full overflow-y-scroll snap-y snap-mandatory scroll-smooth pt-[56px]"
      >
        
        {/* ── SECTION 1: Hero + Globe + Stats ───────────────────────────────── */}
        <section 
          id="hero" 
          className="snap-start snap-always w-full h-[calc(100vh-56px)] min-h-[calc(100vh-56px)] flex flex-col justify-between relative overflow-hidden shrink-0 pb-6"
        >
          {/* Rotating Globe Background (fully unified, rotates in perfect lockstep) */}
          <HeroGlobe />
          
          <div className="absolute inset-0 z-[1] bg-gradient-to-b from-[#050505]/40 via-transparent to-[#050505]" />
          <div className="absolute inset-0 z-[1] bg-gradient-to-r from-[#050505]/60 via-transparent to-[#050505]/60" />

          {/* Hero text */}
          <div className="relative z-10 flex-1 flex items-center justify-center pt-4">
            <div className="text-center max-w-4xl px-6 space-y-4">
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-blue-500/20 bg-blue-500/10 text-blue-400 text-[10px] font-semibold uppercase tracking-widest animate-fade-in-up">
                <span className="relative flex h-1.5 w-1.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 bg-blue-400" />
                  <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-blue-500" />
                </span>
                System Active | Real-Time Monitoring
              </div>

              <h1 className="text-4xl md:text-6xl lg:text-7xl font-extrabold tracking-tighter leading-[1.05] animate-fade-in-up anim-delay-100 text-white">
                Enterprise Grade <br className="hidden md:block" />
                <span className="bg-gradient-to-r from-blue-400 via-cyan-400 to-indigo-400 bg-clip-text text-transparent">
                  Threat Intelligence
                </span>
              </h1>

              <p className="text-sm md:text-base text-slate-400 max-w-xl mx-auto leading-relaxed animate-fade-in-up anim-delay-200">
                Monitor, analyze, and neutralize SSH-based attacks in real-time. CloudSentinel maps adversary behaviors to the
                MITRE ATT&CK framework with an interactive war room dashboard powered by AI.
              </p>

              <div className="flex items-center justify-center gap-3 pt-2 animate-fade-in-up anim-delay-300">
                <Link
                  href="/signin"
                  className="px-6 py-3 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-bold shadow-lg shadow-blue-500/25 hover:shadow-blue-500/40 hover:-translate-y-1 transition-all flex items-center gap-2 text-xs"
                >
                  <Lock size={14} />
                  Access Dashboard
                </Link>
                <a
                  href="#how-it-works"
                  className="px-6 py-3 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 text-white font-semibold text-xs flex items-center gap-1.5 transition-all"
                >
                  Explore Features
                  <ChevronRight size={12} />
                </a>
              </div>
            </div>
          </div>

          {/* Stats Bar */}
          <div className="relative z-10 px-6 md:px-12">
            <div className="max-w-5xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-3">
              <StatCard value="50,000+" label="Threats Analyzed" icon={<Crosshair size={16} className="text-red-400" />} delay="anim-delay-100" />
              <StatCard value="190+" label="Countries Tracked" icon={<Globe size={16} className="text-blue-400" />} delay="anim-delay-200" />
              <StatCard value="<15ms" label="Avg MTTB" icon={<Zap size={16} className="text-amber-400" />} delay="anim-delay-300" />
              <StatCard value="24/7" label="Active Monitoring" icon={<Activity size={16} className="text-emerald-400" />} delay="anim-delay-400" />
            </div>
          </div>
        </section>

        {/* ── SECTION 2: How It Works ────────────────────────────────────────── */}
        <section 
          id="how-it-works" 
          className="snap-start snap-always w-full h-[calc(100vh-56px)] min-h-[calc(100vh-56px)] flex flex-col justify-center items-center py-6 px-6 md:px-12 relative overflow-hidden shrink-0"
        >
          <div className="max-w-5xl mx-auto w-full space-y-8">
            <div className="text-center reveal-on-scroll">
              <p className="text-[10px] font-semibold uppercase tracking-widest text-blue-400 mb-1.5">Active Defense</p>
              <h2 className="text-2xl md:text-4xl font-extrabold tracking-tight text-white">
                Three-Stage Active Defense Pipeline
              </h2>
              <p className="text-xs md:text-sm text-slate-400 mt-2 max-w-xl mx-auto">
                CloudSentinel operates as a layered defense system that captures, analyzes, and responds to SSH-based threats autonomously.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="reveal-on-scroll">
                <PipelineStep
                  step="01"
                  color="text-cyan-400"
                  borderColor="border-cyan-500/20"
                  bgColor="bg-cyan-500/5"
                  icon={<Crosshair size={24} />}
                  title="Detect"
                  description="A production-grade Cowrie SSH honeypot captures attacker sessions, credentials, commands, and SSH client fingerprints (HASSH) in real-time. Every keystroke is recorded."
                />
              </div>
              <div className="reveal-on-scroll">
                <PipelineStep
                  step="02"
                  color="text-blue-400"
                  borderColor="border-blue-500/20"
                  bgColor="bg-blue-500/5"
                  icon={<Brain size={24} />}
                  title="Analyze"
                  description="Captured data is streamed to ClickHouse for high-speed analytics. Each session is automatically mapped to MITRE ATT&CK techniques and fed to an AI-powered analysis engine."
                />
              </div>
              <div className="reveal-on-scroll">
                <PipelineStep
                  step="03"
                  color="text-indigo-400"
                  borderColor="border-indigo-500/20"
                  bgColor="bg-indigo-500/5"
                  icon={<ShieldCheck size={24} />}
                  title="Neutralize"
                  description="The SOAR engine automatically triggers iptables firewall blocks, publishes threat intelligence events, and can execute active defense playbooks - all within milliseconds."
                />
              </div>
            </div>
          </div>
        </section>

        {/* ── SECTION 3: Capabilities ────────────────────────────────────────── */}
        <section 
          id="features" 
          className="snap-start snap-always w-full h-[calc(100vh-56px)] min-h-[calc(100vh-56px)] flex flex-col justify-center items-center py-6 px-6 md:px-12 bg-[#0a0a0a]/30 relative overflow-hidden shrink-0"
        >
          <div className="max-w-5xl mx-auto w-full space-y-6">
            <div className="text-center reveal-on-scroll">
              <p className="text-[10px] font-semibold uppercase tracking-widest text-blue-400 mb-1.5">Capabilities</p>
              <h2 className="text-2xl md:text-4xl font-extrabold tracking-tight text-white">
                Built for Security Operations
              </h2>
              <p className="text-xs md:text-sm text-slate-400 mt-2 max-w-xl mx-auto">
                Every component is designed for real-world threat hunting and incident response workflows.
              </p>
            </div>

            <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
              <div className="reveal-on-scroll"><FeatureCard icon={<Globe className="text-blue-400" size={20} />} title="Global Threat Map" description="Interactive D3.js world map with real-time attack line animations. Click any country to filter by region." tags={["D3.js", "GeoIP", "Real-Time"]} /></div>
              <div className="reveal-on-scroll"><FeatureCard icon={<Terminal className="text-emerald-400" size={20} />} title="Live Session Replay" description="Watch attacker commands execute in a terminal emulator. See both attacker input and honeypot responses." tags={["WebSocket", "Terminal", "Replay"]} /></div>
              <div className="reveal-on-scroll"><FeatureCard icon={<Brain className="text-purple-400" size={20} />} title="MITRE ATT&CK Mapping" description="Automated technique classification maps each session to the MITRE framework. Identify attacker techniques." tags={["MITRE", "TTP"]} /></div>
              <div className="reveal-on-scroll"><FeatureCard icon={<Shield className="text-red-400" size={20} />} title="SOAR Automated Response" description="Security Orchestration triggers iptables blocks within milliseconds of detection. Mean Time To Block averages under 15ms." tags={["SOAR", "iptables"]} /></div>
              <div className="reveal-on-scroll"><FeatureCard icon={<Fingerprint className="text-amber-400" size={20} />} title="HASSH Fingerprinting" description="Unique SSH client fingerprinting identifies attacker toolkits before credentials are even attempted." tags={["HASSH", "Fingerprint"]} /></div>
              <div className="reveal-on-scroll"><FeatureCard icon={<Cpu className="text-cyan-400" size={20} />} title="AI-Powered Analysis" description="Built-in AI assistant explains attacker behavior, suggests MITRE mappings, and can block active IPs." tags={["GPT-4o", "Agent"]} /></div>
            </div>
          </div>
        </section>

        {/* ── SECTION 4: Architecture ────────────────────────────────────────── */}
        <section 
          id="architecture" 
          className="snap-start snap-always w-full h-[calc(100vh-56px)] min-h-[calc(100vh-56px)] flex flex-col justify-center items-center py-6 px-6 md:px-12 relative overflow-hidden shrink-0"
        >
          <div className="max-w-5xl mx-auto w-full space-y-8">
            <div className="text-center reveal-on-scroll">
              <p className="text-[10px] font-semibold uppercase tracking-widest text-blue-400 mb-1.5">System Architecture</p>
              <h2 className="text-2xl md:text-4xl font-extrabold tracking-tight text-white">
                Cloud-Native Defense Stack
              </h2>
              <p className="text-xs md:text-sm text-slate-400 mt-2 max-w-xl mx-auto">
                A horizontally scalable architecture designed for production deployment across multiple cloud regions.
              </p>
            </div>

            <div className="relative reveal-on-scroll px-4 md:px-8 py-4">
              {/* Steady glowing connection pipeline line */}
              <div className="hidden md:block absolute top-1/2 left-[12.5%] right-[12.5%] h-[2px] -translate-y-1/2 bg-blue-500/20 shadow-[0_0_8px_rgba(59,130,246,0.3)] z-0 rounded-full">
                {/* Moving energy packet (runs beautifully left-to-right, no flicker or yellow dots) */}
                <div className="animate-packet-flow" />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-4 gap-4 relative z-10">
                <ArchNode icon={<Server size={24} />} label="SSH Honeypot" tech="Cowrie" description="Captures attacker sessions, credentials, and TTY data on DigitalOcean" color="text-cyan-400" borderColor="border-cyan-500/20" />
                <ArchNode icon={<Database size={24} />} label="Analytics Engine" tech="ClickHouse" description="High-speed columnar storage for real-time query and aggregation" color="text-amber-400" borderColor="border-amber-500/20" />
                <ArchNode icon={<MonitorDot size={24} />} label="Dashboard" tech="Next.js + Socket.io" description="War Room UI with live WebSocket telemetry and AI-powered chat" color="text-blue-400" borderColor="border-blue-500/20" />
                <ArchNode icon={<ShieldCheck size={24} />} label="SOAR Engine" tech="Python + iptables" description="Automated blocking, threat intel publishing, and active playbooks" color="text-red-400" borderColor="border-red-500/20" />
              </div>
            </div>
          </div>
        </section>

        {/* ── SECTION 5: CTA + Footer ────────────────────────────────────────── */}
        <section 
          id="cta" 
          className="snap-start snap-always w-full h-[calc(100vh-56px)] min-h-[calc(100vh-56px)] flex flex-col justify-between pt-12 pb-6 px-6 md:px-12 relative overflow-hidden shrink-0"
        >
          <div className="flex-1 flex items-center justify-center">
            <div className="max-w-4xl mx-auto text-center reveal-on-scroll w-full">
              <div className="rounded-2xl border border-white/10 bg-gradient-to-br from-blue-600/10 via-[#0a0a0a] to-indigo-600/10 p-10 md:p-14 relative overflow-hidden shadow-2xl">
                <div className="absolute -top-24 -right-24 w-48 h-48 bg-blue-500/25 rounded-full blur-3xl" />
                <div className="absolute -bottom-24 -left-24 w-48 h-48 bg-indigo-500/25 rounded-full blur-3xl" />

                <div className="relative z-10 space-y-6">
                  <h2 className="text-3xl md:text-5xl font-extrabold tracking-tight text-white">
                    Ready to See Your Threats?
                  </h2>
                  <p className="text-xs md:text-sm text-slate-400 max-w-lg mx-auto leading-relaxed">
                    Access the CloudSentinel War Room to monitor live attacks, replay attacker sessions, and take automated defensive action - all from a single dashboard.
                  </p>
                  <Link
                    href="/signin"
                    className="inline-flex items-center gap-2 px-6 py-3.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs shadow-lg shadow-blue-500/25 hover:shadow-blue-500/40 hover:-translate-y-0.5 transition-all"
                  >
                    <Lock size={14} />
                    Enter War Room
                    <ArrowRight size={14} />
                  </Link>
                </div>
              </div>
            </div>
          </div>

          {/* Footer */}
          <footer className="border-t border-white/5 pt-6 text-center text-xs text-slate-500">
            <div className="max-w-5xl mx-auto flex flex-col md:flex-row items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <div className="p-1 rounded bg-blue-600 text-white">
                  <Shield size={12} />
                </div>
                <span className="font-semibold text-slate-400 text-xs">CloudSentinel</span>
              </div>
              <p>&copy; {new Date().getFullYear()} CloudSentinel Threat Detection System. All rights reserved.</p>
              <div className="flex gap-4 text-slate-500 text-[10px]">
                <span>FYP Project</span>
                <span>•</span>
                <span>MITRE ATT&CK</span>
              </div>
            </div>
          </footer>
        </section>

      </div>
    </div>
  );
}

// ─── Sub-Components ──────────────────────────────────────────────────────────

function StatCard({ value, label, icon, delay }: { value: string; label: string; icon: React.ReactNode; delay: string }) {
  return (
    <div className={`rounded-xl border border-white/5 bg-[#0a0a0a]/80 backdrop-blur-xl p-3 text-center shadow-lg hover:border-white/10 hover:scale-105 transition-all animate-fade-in-up ${delay}`}>
      <div className="flex justify-center mb-1">{icon}</div>
      <div className="text-lg md:text-xl font-extrabold tracking-tight text-white">{value}</div>
      <div className="text-[9px] text-slate-400 font-medium mt-0.5">{label}</div>
    </div>
  );
}

function PipelineStep({ step, color, borderColor, bgColor, icon, title, description }: {
  step: string; color: string; borderColor: string; bgColor: string; icon: React.ReactNode; title: string; description: string;
}) {
  return (
    <div className={`relative rounded-2xl border ${borderColor} ${bgColor} p-6 transition-all hover:scale-[1.02] hover:shadow-lg hover:shadow-blue-500/5 h-[230px] flex flex-col justify-between`}>
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className={`text-[9px] font-bold uppercase tracking-widest ${color}`}>Step {step}</div>
          <div className={`p-1.5 rounded-lg border ${borderColor} bg-[#050505] ${color}`}>
            {icon}
          </div>
        </div>
        <h3 className="text-base font-bold text-white leading-snug">{title}</h3>
        <p className="text-xs text-slate-400 leading-relaxed line-clamp-4">{description}</p>
      </div>
    </div>
  );
}

function FeatureCard({ icon, title, description, tags }: {
  icon: React.ReactNode; title: string; description: string; tags: string[];
}) {
  return (
    <div className="group flex flex-col p-5 rounded-2xl border border-white/5 bg-white/[0.02] hover:bg-white/[0.04] hover:border-white/10 transition-all hover:-translate-y-0.5 h-[175px] justify-between">
      <div className="space-y-2">
        <div className="flex items-center gap-3">
          <div className="p-1.5 rounded-lg bg-[#050505] border border-white/10 group-hover:scale-105 transition-transform">
            {icon}
          </div>
          <h3 className="text-xs md:text-sm font-bold text-white leading-snug">{title}</h3>
        </div>
        <p className="text-[11px] text-slate-400 leading-relaxed line-clamp-3">{description}</p>
      </div>
      <div className="flex flex-wrap gap-1">
        {tags.map((tag) => (
          <span key={tag} className="text-[8px] font-medium uppercase tracking-wider px-1.5 py-0.5 rounded bg-white/5 text-slate-500 border border-white/5">
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
    <div className={`relative z-10 rounded-2xl border ${borderColor} bg-[#0a0a0a] p-5 text-center transition-all hover:scale-[1.03] hover:shadow-lg hover:shadow-blue-500/5 h-[165px] flex flex-col justify-center`}>
      <div className="space-y-2">
        <div className={`${color} flex justify-center`}>{icon}</div>
        <div>
          <h4 className="font-bold text-xs text-white leading-snug">{label}</h4>
          <div className={`text-[8px] font-semibold uppercase tracking-widest ${color} mt-0.5`}>{tech}</div>
        </div>
        <p className="text-[10px] text-slate-500 leading-relaxed line-clamp-2">{description}</p>
      </div>
    </div>
  );
}
