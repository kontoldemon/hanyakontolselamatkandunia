"use client";

import { useAgent } from "@/lib/AgentContext";
import { Bot, Loader2 } from "lucide-react";

export default function AgentOverlay() {
  const { isExecuting, currentAction } = useAgent();

  if (!isExecuting) return null;

  const borderGradient = `linear-gradient(rgba(0,0,0,0), rgba(0,0,0,0)) padding-box, linear-gradient(var(--bg-angle, 0deg), #3b82f6, #8b5cf6, #ec4899, #3b82f6) border-box`;

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
          0% { box-shadow: 0 0 0 0 rgba(59,130,246,0.5); }
          50% { box-shadow: 0 0 0 12px rgba(139,92,246,0); }
          100% { box-shadow: 0 0 0 0 rgba(236,72,153,0); }
        }
        @property --bg-angle {
          syntax: "<angle>";
          initial-value: 0deg;
          inherits: false;
        }
      `}</style>

      <div
        className="fixed inset-0 z-[95] pointer-events-auto"
        style={{ animation: "agent-fade-in 0.5s ease-out forwards" }}
      >

        {/* Top edge */}
        <div
          className="absolute top-2 md:top-3 left-2 md:left-3 right-2 md:right-3 h-[3px] rounded-t-2xl md:rounded-t-3xl pointer-events-none"
          style={{
            background: borderGradient,
            borderTop: "3px solid transparent",
            animation: "agent-gradient-spin 4s linear infinite",
            boxShadow: "0 0 16px rgba(59, 130, 246, 0.5), 0 0 40px rgba(139, 92, 246, 0.2)",
          }}
        />
        {/* Bottom edge */}
        <div
          className="absolute bottom-2 md:bottom-3 left-2 md:left-3 right-2 md:right-3 h-[3px] rounded-b-2xl md:rounded-b-3xl pointer-events-none"
          style={{
            background: borderGradient,
            borderBottom: "3px solid transparent",
            animation: "agent-gradient-spin 4s linear infinite",
            boxShadow: "0 0 16px rgba(59, 130, 246, 0.5), 0 0 40px rgba(139, 92, 246, 0.2)",
          }}
        />
        {/* Left edge */}
        <div
          className="absolute top-2 md:top-3 bottom-2 md:bottom-3 left-2 md:left-3 w-[3px] rounded-l-2xl md:rounded-l-3xl pointer-events-none"
          style={{
            background: borderGradient,
            borderLeft: "3px solid transparent",
            animation: "agent-gradient-spin 4s linear infinite",
            boxShadow: "0 0 16px rgba(59, 130, 246, 0.5), 0 0 40px rgba(139, 92, 246, 0.2)",
          }}
        />
        {/* Right edge */}
        <div
          className="absolute top-2 md:top-3 bottom-2 md:bottom-3 right-2 md:right-3 w-[3px] rounded-r-2xl md:rounded-r-3xl pointer-events-none"
          style={{
            background: borderGradient,
            borderRight: "3px solid transparent",
            animation: "agent-gradient-spin 4s linear infinite",
            boxShadow: "0 0 16px rgba(59, 130, 246, 0.5), 0 0 40px rgba(139, 92, 246, 0.2)",
          }}
        />

        {/* Floating status pill at top-center */}
        <div className="absolute top-6 left-1/2 -translate-x-1/2 pointer-events-auto">
          <div
            className="flex items-center gap-3 px-5 py-2.5 rounded-full border border-white/20 text-white text-sm font-medium shadow-2xl"
            style={{
              background: "linear-gradient(var(--bg-angle, 135deg), rgba(59,130,246,0.9), rgba(139,92,246,0.9), rgba(236,72,153,0.9), rgba(59,130,246,0.9))",
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
