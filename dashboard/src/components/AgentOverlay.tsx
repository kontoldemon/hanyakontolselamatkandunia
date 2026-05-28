"use client";

import { useEffect, useState } from "react";
import { useAgent } from "@/lib/AgentContext";
import { Bot, Loader2 } from "lucide-react";

export default function AgentOverlay() {
  const { isExecuting, currentAction } = useAgent();
  const [shouldRender, setShouldRender] = useState(isExecuting);
  const [isFadingOut, setIsFadingOut] = useState(false);
  const [savedAction, setSavedAction] = useState(currentAction);

  useEffect(() => {
    let t1: NodeJS.Timeout;
    let t2: NodeJS.Timeout;
    if (isExecuting) {
      t1 = setTimeout(() => {
        setShouldRender(true);
        setIsFadingOut(false);
        if (currentAction) {
          setSavedAction(currentAction);
        }
      }, 0);
    } else {
      t1 = setTimeout(() => {
        setIsFadingOut(true);
        t2 = setTimeout(() => {
          setShouldRender(false);
          setIsFadingOut(false);
        }, 500);
      }, 0);
    }
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
    };
  }, [isExecuting, currentAction]);

  if (!shouldRender) return null;

  return (
    <>
      <style>{`
        @keyframes agent-gradient-spin {
          0% { --bg-angle: 0deg; }
          100% { --bg-angle: 360deg; }
        }
        @keyframes agent-fade-in {
          0% { opacity: 0; transform: scale(1.015); }
          100% { opacity: 1; transform: scale(1); }
        }
        @keyframes agent-fade-out {
          0% { opacity: 1; transform: scale(1); }
          100% { opacity: 0; transform: scale(1.015); }
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

      {/* Main cinematic wrapper handling seamless fade-in & fade-out */}
      <div
        className="fixed inset-0 z-[95] pointer-events-none"
        style={{
          animation: `${isFadingOut ? "agent-fade-out" : "agent-fade-in"} 0.5s cubic-bezier(0.16, 1, 0.3, 1) forwards`
        }}
      >
        {/* Edge frame glow with zero gap and premium inset shadow */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            border: "6px solid transparent",
            borderImage: "linear-gradient(var(--bg-angle, 0deg), #3b82f6, #8b5cf6, #ec4899, #f59e0b, #3b82f6) 1",
            animation: "agent-gradient-spin 5s linear infinite",
            boxShadow: "inset 0 0 20px rgba(59, 130, 246, 0.45), inset 0 0 50px rgba(139, 92, 246, 0.25)",
          }}
        />

        {/* Floating status pill at top-center */}
        <div className="absolute top-6 left-1/2 -translate-x-1/2 z-[96] pointer-events-auto">
          <div
            className="flex items-center gap-3 px-5 py-2.5 rounded-full border border-white/20 text-white text-sm font-medium shadow-2xl"
            style={{
              background: "linear-gradient(var(--bg-angle, 135deg), rgba(59,130,246,0.95), rgba(139,92,246,0.95), rgba(236,72,153,0.95), rgba(245,158,11,0.95), rgba(59,130,246,0.95))",
              animation: "agent-gradient-spin 5s linear infinite, agent-pulse-ring 2.5s ease infinite",
              backdropFilter: "blur(16px)",
            }}
          >
            <Bot size={18} className="shrink-0 animate-bounce" />
            <Loader2 size={14} className="animate-spin shrink-0 text-blue-200" />
            <span className="whitespace-nowrap font-semibold tracking-wide">
              {savedAction ? savedAction.label : "Agent in action..."}
            </span>
          </div>
        </div>
      </div>
    </>
  );
}
