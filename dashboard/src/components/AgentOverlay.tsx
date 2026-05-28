"use client";

import { useAgent } from "@/lib/AgentContext";
import { Bot, Loader2 } from "lucide-react";

export default function AgentOverlay() {
  const { isExecuting, currentAction } = useAgent();

  if (!isExecuting) return null;

  return (
    <>
      <style>{`
        @keyframes agent-gradient-spin {
          0% { --bg-angle: 0deg; }
          100% { --bg-angle: 360deg; }
        }
        @keyframes agent-fade-in {
          0% { opacity: 0; }
          100% { opacity: 1; }
        }
        @keyframes agent-pulse-ring {
          0% { box-shadow: 0 0 0 0 rgba(59,101,202,0.5); }
          50% { box-shadow: 0 0 0 12px rgba(207,58,122,0); }
          100% { box-shadow: 0 0 0 0 rgba(244,80,81,0); }
        }
        @property --bg-angle {
          syntax: "<angle>";
          initial-value: 0deg;
          inherits: false;
        }
      `}</style>

      {/* Full-screen overlay container — pointer-events-auto so it blocks user clicks from disturbing the agent's programmatic flow */}
      <div
        className="fixed inset-0 z-[95] pointer-events-auto"
        style={{ animation: "agent-fade-in 0.5s ease-out forwards" }}
      >


        {/* Gradient edge glow with smooth corners */}
        <div
          className="absolute inset-1.5 md:inset-3 rounded-2xl md:rounded-3xl pointer-events-none"
          style={{
            border: "3px solid transparent",
            background: `
              linear-gradient(rgba(0,0,0,0), rgba(0,0,0,0)) padding-box,
              linear-gradient(var(--bg-angle, 0deg), #3b82f6, #8b5cf6, #ec4899, #3b82f6) border-box
            `,
            animation: "agent-gradient-spin 4s linear infinite",
            boxShadow: "0 0 20px rgba(59, 130, 246, 0.3), inset 0 0 20px rgba(59, 130, 246, 0.3)",
          }}
        />

        {/* Floating status pill at top-center */}
        <div className="absolute top-6 left-1/2 -translate-x-1/2 pointer-events-auto">
          <div
            className="flex items-center gap-3 px-5 py-2.5 rounded-full border border-white/20 text-white text-sm font-medium shadow-2xl"
            style={{
              background: "linear-gradient(var(--bg-angle, 135deg), rgba(59,101,202,0.9), rgba(207,58,122,0.9), rgba(244,80,81,0.9), rgba(59,101,202,0.9))",
              animation: "agent-gradient-spin 4s linear infinite, agent-pulse-ring 2s ease infinite",
              backdropFilter: "blur(16px)",
            }}
          >
            <Bot size={18} className="shrink-0" />
            <Loader2 size={14} className="animate-spin shrink-0" />
            <span className="whitespace-nowrap">
              {currentAction ? currentAction.label : "Agent executing..."}
            </span>
          </div>
        </div>
      </div>
    </>
  );
}
