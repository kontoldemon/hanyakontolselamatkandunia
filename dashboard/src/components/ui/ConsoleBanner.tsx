"use client";

import { useEffect } from "react";

export default function ConsoleBanner() {
  useEffect(() => {
    if (typeof window === "undefined") return;
    const win = window as unknown as { __cloudsentinel_console_logged?: boolean };
    if (win.__cloudsentinel_console_logged) return;
    win.__cloudsentinel_console_logged = true;

    const badgeMain = [
      "background: #2563eb;",
      "color: #ffffff;",
      "font-weight: 800;",
      "font-size: 11px;",
      "padding: 3px 8px;",
      "border-radius: 4px 0 0 4px;",
      "font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;",
    ].join(" ");

    const badgeSub = [
      "background: #090d16;",
      "color: #38bdf8;",
      "font-weight: 600;",
      "font-size: 11px;",
      "padding: 3px 8px;",
      "border: 1px solid rgba(56, 189, 248, 0.3);",
      "border-left: none;",
      "border-radius: 0 4px 4px 0;",
      "font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;",
    ].join(" ");

    console.log(
      "%cCLOUDSENTINEL%cACTIVE TELEMETRY & THREAT CONTAINMENT",
      badgeMain,
      badgeSub
    );
  }, []);

  return null;
}
