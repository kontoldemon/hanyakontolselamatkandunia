"use client";

import { useAgent } from "@/lib/AgentContext";
import { Bot, Loader2 } from "lucide-react";

export default function AgentOverlay() {
  const { isExecuting, currentAction } = useAgent();

  if (!isExecuting) return null;

  return (
    <>
      <style>{`
        @keyframes agent-border-glow {
          0% { opacity: 0.7; filter: hue-rotate(0deg); }
          50% { opacity: 1; filter: hue-rotate(15deg); }
          100% { opacity: 0.7; filter: hue-rotate(0deg); }
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
      `}</style>

      {/* Full-screen overlay container — pointer-events-auto so it blocks user clicks from disturbing the agent's programmatic flow */}
      <div
        className="fixed inset-0 z-[95] pointer-events-auto"
        style={{ animation: "agent-fade-in 0.5s ease-out forwards" }}
      >
        {/* Dimmed backdrop */}
        <div className="absolute inset-0 bg-black/35 backdrop-blur-[2px]" />

        {/* Gradient edge glow — top */}
        <div
          className="absolute top-0 left-0 right-0 h-2"
          style={{
            background: "linear-gradient(90deg, #3b65ca, #cf3a7a, #f45051, #cf3a7a, #3b65ca)",
            backgroundSize: "300% 100%",
            animation: "agent-border-glow 3s ease infinite",
            boxShadow: "0 0 30px 8px rgba(207,58,122,0.4), 0 0 60px 16px rgba(59,101,202,0.2)",
          }}
        />
        {/* Gradient edge glow — bottom */}
        <div
          className="absolute bottom-0 left-0 right-0 h-2"
          style={{
            background: "linear-gradient(90deg, #f45051, #cf3a7a, #3b65ca, #cf3a7a, #f45051)",
            backgroundSize: "300% 100%",
            animation: "agent-border-glow 3s ease infinite",
            boxShadow: "0 0 30px 8px rgba(207,58,122,0.4), 0 0 60px 16px rgba(59,101,202,0.2)",
          }}
        />
        {/* Gradient edge glow — left */}
        <div
          className="absolute top-0 bottom-0 left-0 w-2"
          style={{
            background: "linear-gradient(180deg, #3b65ca, #cf3a7a, #f45051, #cf3a7a, #3b65ca)",
            backgroundSize: "100% 300%",
            animation: "agent-border-glow 3s ease infinite",
            boxShadow: "0 0 30px 8px rgba(207,58,122,0.4), 0 0 60px 16px rgba(59,101,202,0.2)",
          }}
        />
        {/* Gradient edge glow — right */}
        <div
          className="absolute top-0 bottom-0 right-0 w-2"
          style={{
            background: "linear-gradient(180deg, #f45051, #cf3a7a, #3b65ca, #cf3a7a, #f45051)",
            backgroundSize: "100% 300%",
            animation: "agent-border-glow 3s ease infinite",
            boxShadow: "0 0 30px 8px rgba(207,58,122,0.4), 0 0 60px 16px rgba(59,101,202,0.2)",
          }}
        />

        {/* Floating status pill at top-center */}
        <div className="absolute top-6 left-1/2 -translate-x-1/2 pointer-events-auto">
          <div
            className="flex items-center gap-3 px-5 py-2.5 rounded-full border border-white/20 text-white text-sm font-medium shadow-2xl"
            style={{
              background: "linear-gradient(135deg, rgba(59,101,202,0.9), rgba(207,58,122,0.9), rgba(244,80,81,0.9))",
              animation: "agent-pulse-ring 2s ease infinite",
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
