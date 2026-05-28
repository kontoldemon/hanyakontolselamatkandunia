"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useRouter, usePathname } from "next/navigation";
import type { AgentAction } from "@/lib/agentActions";
import { UI_TARGETS } from "@/lib/agentActions";

// ─── Context Shape ──────────────────────────────────────────────────────────

interface AgentContextValue {
  isExecuting: boolean;
  currentAction: AgentAction | null;
  executeAction: (action: AgentAction) => Promise<string>;
  cancelAction: () => void;
  registerCommand: (target: string, handler: (value: string) => void) => void;
  unregisterCommand: (target: string) => void;
}

const AgentContext = createContext<AgentContextValue>({
  isExecuting: false,
  currentAction: null,
  executeAction: async () => "",
  cancelAction: () => {},
  registerCommand: () => {},
  unregisterCommand: () => {},
});

export function useAgent() {
  return useContext(AgentContext);
}

// ─── Hook for components to register command handlers ────────────────────────

export function useAgentCommand(target: string, handler: (value: string) => void) {
  const { registerCommand, unregisterCommand } = useAgent();
  const handlerRef = useRef(handler);
  handlerRef.current = handler;

  useEffect(() => {
    const stableHandler = (v: string) => handlerRef.current(v);
    registerCommand(target, stableHandler);
    return () => unregisterCommand(target);
  }, [target, registerCommand, unregisterCommand]);
}

// ─── Provider ───────────────────────────────────────────────────────────────

export function AgentProvider({ children }: { children: ReactNode }) {
  const [isExecuting, setIsExecuting] = useState(false);
  const [currentAction, setCurrentAction] = useState<AgentAction | null>(null);
  const abortRef = useRef(false);
  const router = useRouter();
  const pathname = usePathname();
  const pathnameRef = useRef(pathname);
  pathnameRef.current = pathname;

  // Command handler registry
  const commandHandlers = useRef<Map<string, (value: string) => void>>(new Map());

  const registerCommand = useCallback((target: string, handler: (value: string) => void) => {
    commandHandlers.current.set(target, handler);
  }, []);

  const unregisterCommand = useCallback((target: string) => {
    commandHandlers.current.delete(target);
  }, []);

  const dispatchCommand = useCallback((target: string, value: string): boolean => {
    const handler = commandHandlers.current.get(target);
    if (handler) {
      handler(value);
      return true;
    }
    return false;
  }, []);

  const wait = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

  // Retry dispatching a command (handlers may not be registered yet after navigation)
  const dispatchWithRetry = useCallback(
    async (target: string, value: string, retries = 5, delay = 400): Promise<boolean> => {
      for (let i = 0; i < retries; i++) {
        if (dispatchCommand(target, value)) return true;
        await wait(delay);
      }
      return false;
    },
    [dispatchCommand],
  );

  const executeAction = useCallback(
    async (action: AgentAction): Promise<string> => {
      abortRef.current = false;
      setCurrentAction(action);
      setIsExecuting(true);

      // Dramatic entrance
      await wait(800);
      if (abortRef.current) {
        setIsExecuting(false);
        setCurrentAction(null);
        return "Action cancelled.";
      }

      let result = "";

      try {
        switch (action.type) {
          // ── Navigation Actions ──
          case "navigate_session": {
            const ip = action.params.value;
            router.push(`/sessions?focusIp=${encodeURIComponent(ip)}`);
            await wait(1200);
            result = `Navigated to Sessions and focused on attacker ${ip}. You can now see full session details, terminal replay, SOAR action status, and MITRE ATT&CK mappings.`;
            break;
          }

          case "navigate_page": {
            const path = action.params.value || "/";
            router.push(path);
            await wait(1000);
            const names: Record<string, string> = { "/": "War Room", "/sessions": "Sessions", "/intelligence": "Intelligence", "/settings": "Settings" };
            result = `Navigated to ${names[path] ?? path}. You're now viewing the latest data.`;
            break;
          }

          case "show_threat_map": {
            router.push("/");
            await wait(1200);
            result = "Navigated to the War Room. The Global Threat Map is now visible with real-time attack indicators.";
            break;
          }

          // ── API Actions ──
          case "block_ip": {
            const ip = action.params.value;
            try {
              const res = await fetch("/api/cloudsentinel/block-ip", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ ip, ttl: 3600, reason: "agent-assisted" }),
              });
              const data = await res.json();
              result = data.ok
                ? `IP ${ip} has been successfully blocked at the sensor firewall (iptables). The block will expire in 1 hour.`
                : `Block attempt for ${ip} returned: ${data.error ?? "unknown error"}.`;
            } catch {
              result = `Network error while trying to block ${ip}. Verify sensor status in Settings.`;
            }
            break;
          }

          case "export_data": {
            router.push("/");
            await wait(800);
            result = "Navigated to War Room. Click the 'Export' button in the top-right corner to download the sensor JSON payload.";
            break;
          }

          case "toggle_exposure": {
            // Navigate to settings first if not there
            if (pathnameRef.current !== "/settings") {
              router.push("/settings");
              await wait(1200);
            }
            try {
              const res = await fetch("/api/cloudsentinel/exposure", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ enabled: true }), // toggle — backend decides
              });
              const data = await res.json();
              result = data.ok
                ? `Honeypot exposure has been ${data.paused ? "paused" : "resumed"}. Admin dashboard remains online.`
                : `Exposure toggle failed: ${data.error ?? "unknown error"}.`;
            } catch {
              result = "Network error while toggling exposure. Verify the sensor is online.";
            }
            break;
          }

          // ── Generic UI Command ──
          case "ui_command": {
            const target = action.params.target ?? "";
            const value = action.params.value ?? "toggle";

            // Determine target page and navigate if needed
            const meta = UI_TARGETS[target];
            const targetPage = meta?.page ?? "/";

            // "*" means the component is globally mounted (e.g. sidebar) — no navigation needed
            if (targetPage !== "*" && pathnameRef.current !== targetPage) {
              router.push(targetPage);
              await wait(1500); // wait for page mount and handler registration
            }

            // Dispatch to the registered handler
            const dispatched = await dispatchWithRetry(target, value);
            await wait(400);

            if (dispatched) {
              const friendlyLabel = meta?.label ?? target;
              result = `Successfully updated ${friendlyLabel}${value !== "toggle" ? ` to "${value}"` : ""}.`;
            } else {
              result = `Could not find the UI control "${target}". The component may not be mounted yet.`;
            }
            break;
          }

          default:
            result = "Unknown action type.";
        }
      } catch (err) {
        result = `Action failed: ${err instanceof Error ? err.message : "unknown error"}`;
      }

      await wait(600);
      setIsExecuting(false);
      setCurrentAction(null);
      return result;
    },
    [router, dispatchWithRetry],
  );

  const cancelAction = useCallback(() => {
    abortRef.current = true;
    setIsExecuting(false);
    setCurrentAction(null);
  }, []);

  return (
    <AgentContext.Provider
      value={{ isExecuting, currentAction, executeAction, cancelAction, registerCommand, unregisterCommand }}
    >
      {children}
    </AgentContext.Provider>
  );
}
