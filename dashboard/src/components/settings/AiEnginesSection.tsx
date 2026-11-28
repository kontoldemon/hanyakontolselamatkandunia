"use client";

import { Bot, Eye, EyeOff, Shield, Sparkles } from "lucide-react";
import CustomDropdown from "@/components/ui/CustomDropdown";
import ToggleSwitch from "./ToggleSwitch";

interface AiEnginesSectionProps {
    copilotProvider: string;
    setCopilotProvider: (v: string) => void;
    copilotModel: string;
    setCopilotModel: (v: string) => void;
    copilotApiKey: string;
    setCopilotApiKey: (v: string) => void;
    hasCopilotKey: boolean;
    showCopilotKey: boolean;
    setShowCopilotKey: (v: boolean) => void;
    honeypotLlmMode: string;
    setHoneypotLlmMode: (v: string) => void;
    fallbackChain: string;
    setFallbackChain: (v: string) => void;
    hourlyLimit: number;
    setHourlyLimit: (v: number) => void;
    promptSanitization: boolean;
    setPromptSanitization: (v: boolean) => void;
}

export default function AiEnginesSection({
    copilotProvider,
    setCopilotProvider,
    copilotModel,
    setCopilotModel,
    copilotApiKey,
    setCopilotApiKey,
    hasCopilotKey,
    showCopilotKey,
    setShowCopilotKey,
    honeypotLlmMode,
    setHoneypotLlmMode,
    fallbackChain,
    setFallbackChain,
    hourlyLimit,
    setHourlyLimit,
    promptSanitization,
    setPromptSanitization,
}: AiEnginesSectionProps) {
    return (
        <section id="sec-llm" className="space-y-3.5 scroll-mt-2 animate-in fade-in duration-150">
            <div className="space-y-3.5">
                {/* Copilot */}
                <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-xs overflow-hidden">
                    <div className="px-4 py-2.5 sm:px-5 border-b border-slate-100 dark:border-white/5 bg-slate-50/50 dark:bg-white/[0.015]">
                        <h3 className="font-display font-semibold text-xs tracking-tight text-slate-900 dark:text-white flex items-center gap-2">
                            <Bot size={14} className="text-blue-500" /> Security Analyst Copilot
                        </h3>
                    </div>
                    <div className="divide-y divide-slate-100 dark:divide-white/5">
                        <div className="px-4 py-3 sm:py-2.5 sm:px-5 flex flex-col items-stretch sm:flex-row sm:items-center sm:justify-between gap-2.5 sm:gap-3">
                            <div className="min-w-0 sm:pr-2">
                                <label className="text-xs font-semibold text-slate-900 dark:text-white block sm:truncate">AI Provider</label>
                                <p className="text-[11px] text-slate-500 dark:text-slate-400 sm:truncate">Copilot cloud intelligence provider.</p>
                            </div>
                            <div className="w-full sm:w-56 shrink-0">
                                <CustomDropdown
                                    options={[
                                        { label: "Google Gemini (Recommended)", value: "gemini" },
                                        { label: "Groq Cloud (Ultra-Fast)", value: "groq" },
                                        { label: "OpenAI (GPT-4o)", value: "openai" },
                                        { label: "Anthropic Claude", value: "anthropic" },
                                        { label: "LiteLLM Unified Gateway", value: "litellm" },
                                    ]}
                                    value={copilotProvider}
                                    onChange={setCopilotProvider}
                                />
                            </div>
                        </div>

                        <div className="px-4 py-3 sm:py-2.5 sm:px-5 flex flex-col items-stretch sm:flex-row sm:items-center sm:justify-between gap-2.5 sm:gap-3">
                            <div className="min-w-0 sm:pr-2">
                                <label className="text-xs font-semibold text-slate-900 dark:text-white block sm:truncate">Primary Model</label>
                                <p className="text-[11px] text-slate-500 dark:text-slate-400 sm:truncate">Analyst evaluation model checkpoint.</p>
                            </div>
                            <div className="w-full sm:w-56 shrink-0">
                                <CustomDropdown
                                    options={[
                                        { label: "openai/deepseek-v4.1-flash (OpenCode Go)", value: "openai/deepseek-v4.1-flash" },
                                        { label: "gemini/gemini-2.0-flash", value: "gemini/gemini-2.0-flash" },
                                        { label: "groq/llama-3.3-70b-versatile", value: "groq/llama-3.3-70b-versatile" },
                                        { label: "openai/gpt-4o-mini", value: "openai/gpt-4o-mini" },
                                        { label: "anthropic/claude-3-5-sonnet", value: "anthropic/claude-3-5-sonnet" },
                                    ]}
                                    value={copilotModel}
                                    onChange={setCopilotModel}
                                />
                            </div>
                        </div>

                        <div className="px-4 py-3 sm:py-2.5 sm:px-5 flex flex-col items-stretch sm:flex-row sm:items-center sm:justify-between gap-2.5 sm:gap-3">
                            <div className="min-w-0 sm:pr-2">
                                <label className="text-xs font-semibold text-slate-900 dark:text-white block sm:truncate">API Key</label>
                                <p className="text-[11px] text-slate-500 dark:text-slate-400 sm:truncate">
                                    {hasCopilotKey ? "Key saved. Type a new key only to replace it." : "Inference authentication key."}
                                </p>
                            </div>
                            <div className="w-full sm:w-56 shrink-0 relative flex items-center">
                                <input
                                    type={showCopilotKey ? "text" : "password"}
                                    value={copilotApiKey}
                                    onChange={(e) => setCopilotApiKey(e.target.value)}
                                    placeholder={hasCopilotKey ? "Saved — type to replace" : "AIzaSy... / gsk_..."}
                                    className="w-full h-10 sm:h-8 rounded-lg bg-slate-50/80 dark:bg-white/[0.04] border border-slate-200 dark:border-white/10 pl-3 pr-10 text-xs font-mono text-slate-900 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-500 outline-none focus:ring-1 focus:ring-blue-500 transition-all"
                                />
                                {(!hasCopilotKey || copilotApiKey) && (
                                    <button
                                        type="button"
                                        onClick={() => setShowCopilotKey(!showCopilotKey)}
                                        className="absolute right-0.5 flex h-9 w-9 items-center justify-center text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors cursor-pointer"
                                        title={showCopilotKey ? "Hide key" : "Show key"}
                                    >
                                        {showCopilotKey ? <EyeOff size={13} /> : <Eye size={13} />}
                                    </button>
                                )}
                            </div>
                        </div>
                    </div>
                </div>

                {/* Honeypot VFS */}
                <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-xs overflow-hidden">
                    <div className="px-4 py-2.5 sm:px-5 border-b border-slate-100 dark:border-white/5 bg-slate-50/50 dark:bg-white/[0.015]">
                        <h3 className="font-display font-semibold text-xs tracking-tight text-slate-900 dark:text-white flex items-center gap-2">
                            <Sparkles size={14} className="text-purple-500" /> Honeypot Deception Engine (VFS)
                        </h3>
                    </div>
                    <div className="divide-y divide-slate-100 dark:divide-white/5">
                        <div className="px-4 py-3 sm:py-2.5 sm:px-5 flex flex-col items-stretch sm:flex-row sm:items-center sm:justify-between gap-2.5 sm:gap-3">
                            <div className="min-w-0 sm:pr-2">
                                <label className="text-xs font-semibold text-slate-900 dark:text-white block sm:truncate">Emulation Mode</label>
                                <p className="text-[11px] text-slate-500 dark:text-slate-400 sm:truncate">Terminal output generation mode.</p>
                            </div>
                            <div className="w-full sm:w-56 shrink-0">
                                <CustomDropdown
                                    options={[
                                        { label: "Dynamic VFS Terminal Emulation", value: "dynamic" },
                                        { label: "Deterministic Offline Fallback", value: "deterministic" },
                                    ]}
                                    value={honeypotLlmMode}
                                    onChange={setHoneypotLlmMode}
                                />
                            </div>
                        </div>

                        <div className="px-4 py-3 sm:py-2.5 sm:px-5 flex flex-col items-stretch sm:flex-row sm:items-center sm:justify-between gap-2.5 sm:gap-3">
                            <div className="min-w-0 sm:pr-2">
                                <label className="text-xs font-semibold text-slate-900 dark:text-white block sm:truncate">Fallback Models</label>
                                <p className="text-[11px] text-slate-500 dark:text-slate-400 sm:truncate">Failover model sequence (CSV).</p>
                            </div>
                            <div className="w-full sm:w-56 shrink-0">
                                <input
                                    type="text"
                                    value={fallbackChain}
                                    onChange={(e) => setFallbackChain(e.target.value)}
                                    className="w-full h-10 sm:h-8 rounded-lg bg-slate-50/80 dark:bg-white/[0.04] border border-slate-200 dark:border-white/10 px-3 text-xs font-mono text-slate-900 dark:text-white placeholder:text-slate-400 dark:placeholder:text-slate-500 outline-none focus:ring-1 focus:ring-blue-500 transition-all"
                                />
                            </div>
                        </div>

                    </div>
                </div>

                {/* Guardrails */}
                <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-slate-200 dark:border-white/5 shadow-xs overflow-hidden">
                    <div className="px-4 py-2.5 sm:px-5 border-b border-slate-100 dark:border-white/5 bg-slate-50/50 dark:bg-white/[0.015]">
                        <h3 className="font-display font-semibold text-xs tracking-tight text-slate-900 dark:text-white flex items-center gap-2">
                            <Shield size={14} className="text-purple-500" /> Inference Guardrails &amp; Quota Controls
                        </h3>
                    </div>
                    <div className="divide-y divide-slate-100 dark:divide-white/5">
                        <div className="px-4 py-3 sm:py-2.5 sm:px-5 flex flex-col items-stretch sm:flex-row sm:items-center sm:justify-between gap-2.5 sm:gap-3">
                            <div className="min-w-0 sm:pr-2">
                                <label className="text-xs font-semibold text-slate-900 dark:text-white block sm:truncate">Hourly Request Budget</label>
                                <p className="text-[11px] text-slate-500 dark:text-slate-400 sm:truncate">Prevents runaway API credit depletion.</p>
                            </div>
                            <div className="w-full sm:w-56 flex items-center gap-3 shrink-0">
                                <input
                                    type="range"
                                    min="10"
                                    max="1000"
                                    step="10"
                                    value={hourlyLimit}
                                    onChange={(e) => setHourlyLimit(parseInt(e.target.value, 10))}
                                    style={{
                                        background: `linear-gradient(to right, rgb(59 130 246) 0%, rgb(59 130 246) ${Math.round(((hourlyLimit - 10) / (1000 - 10)) * 100)}%, rgba(148, 163, 184, 0.2) ${Math.round(((hourlyLimit - 10) / (1000 - 10)) * 100)}%, rgba(148, 163, 184, 0.2) 100%)`,
                                    }}
                                    className="w-full h-1 rounded-full appearance-none cursor-pointer outline-none [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-2.5 [&::-webkit-slider-thumb]:h-2.5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-blue-500 [&::-webkit-slider-thumb]:hover:scale-125 [&::-webkit-slider-thumb]:transition-all"
                                />
                                <span className="font-mono text-xs font-bold text-blue-500 w-14 text-right shrink-0">{hourlyLimit}/hr</span>
                            </div>
                        </div>

                        <div className="px-4 py-3 sm:py-2.5 sm:px-5 flex items-center justify-between gap-3">
                            <div className="min-w-0 pr-2">
                                <label className="text-xs font-semibold text-slate-900 dark:text-white block sm:truncate">Prompt Sanitization</label>
                                <p className="text-[11px] text-slate-500 dark:text-slate-400 sm:truncate">Strips canary tokens and sensitive host fingerprints.</p>
                            </div>
                            <ToggleSwitch checked={promptSanitization} onChange={setPromptSanitization} />
                        </div>
                    </div>
                </div>
            </div>
        </section>
    );
}
