import { NextResponse } from "next/server";
import { adminApiConfig, adminApiConfigError } from "@/lib/adminApi";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// In-memory runtime store for dashboard UI configuration (fallback if admin API unavailable)
let runtimeLlmConfig = {
  copilotProvider: "Google Gemini",
  copilotModel: "gemini/gemini-2.0-flash",
  copilotApiKey: process.env.GEMINI_API_KEY || process.env.LLM_API_KEY || "",
  honeypotLlmMode: "Dynamic VFS Terminal Emulation",
  honeypotProvider: "Inherit from Copilot",
  honeypotModel: "gemini/gemini-2.0-flash",
  honeypotApiKey: "",
  useCopilotKeyForHoneypot: true,
  fallbackChain: "groq/llama-3.3-70b-versatile, openai/gpt-4o-mini",
  maxOutputChars: 4000,
  hourlyLimit: 200,
  updatedAt: new Date().toISOString(),
};

export async function GET() {
  // Mask API keys for display security
  const maskKey = (k: string) => {
    if (!k || k.length < 8) return k ? "••••••••" : "";
    return `${k.slice(0, 4)}••••••••${k.slice(-4)}`;
  };

  const { copilotApiKey, honeypotApiKey, ...safeConfig } = runtimeLlmConfig;

  return NextResponse.json({
    ok: true,
    config: {
      ...safeConfig,
      copilotApiKeyMasked: maskKey(copilotApiKey),
      honeypotApiKeyMasked: maskKey(honeypotApiKey),
      hasCopilotKey: Boolean(copilotApiKey),
      hasHoneypotKey: Boolean(
        runtimeLlmConfig.useCopilotKeyForHoneypot
          ? copilotApiKey
          : honeypotApiKey
      ),
    },
  });
}

export async function POST(request: Request) {
  try {
    const body = (await request.json().catch(() => ({}))) as Partial<typeof runtimeLlmConfig>;

    // Blank key fields keep the existing secret; the GET response never sends it back.
    runtimeLlmConfig = {
      ...runtimeLlmConfig,
      ...body,
      copilotApiKey: typeof body.copilotApiKey === "string" && body.copilotApiKey.trim()
        ? body.copilotApiKey.trim()
        : runtimeLlmConfig.copilotApiKey,
      honeypotApiKey: typeof body.honeypotApiKey === "string" && body.honeypotApiKey.trim()
        ? body.honeypotApiKey.trim()
        : runtimeLlmConfig.honeypotApiKey,
      updatedAt: new Date().toISOString(),
    };

    // Forward to sensor admin API if available
    const configError = adminApiConfigError();
    if (!configError) {
      try {
        const { baseUrl, headers } = adminApiConfig();
        await fetch(new URL("/llm/config", baseUrl), {
          method: "POST",
          headers: { "Content-Type": "application/json", ...headers },
          body: JSON.stringify({
            provider: runtimeLlmConfig.copilotProvider,
            model: runtimeLlmConfig.copilotModel,
            api_key: runtimeLlmConfig.copilotApiKey,
            honeypot_model: runtimeLlmConfig.honeypotModel,
            fallback_models: runtimeLlmConfig.fallbackChain.split(",").map((s: string) => s.trim()),
          }),
          signal: AbortSignal.timeout(3000),
        }).catch(() => null);
      } catch {
        // Silently tolerate if sensor offline
      }
    }

    return NextResponse.json({
      ok: true,
      message: "LLM configuration applied to Copilot and Honeypot Deception Engine.",
      updatedAt: runtimeLlmConfig.updatedAt,
    });
  } catch (error) {
    return NextResponse.json(
      { ok: false, error: error instanceof Error ? error.message : "Failed to save configuration" },
      { status: 400 }
    );
  }
}
