import type { Metadata } from "next";
import LandingPage from "@/components/landing/LandingPage";

export const metadata: Metadata = {
  title: "CloudSentinel",
  description:
    "SSH honeypot dashboard for real-time intrusion telemetry, HASSH fingerprinting, MITRE ATT&CK mapping, and automated firewall response.",
  keywords: [
    "SSH Honeypot",
    "Threat Intelligence",
    "HASSH",
    "MITRE ATT&CK",
    "SOAR",
    "ClickHouse",
  ],
};

export default function Page() {
  return <LandingPage />;
}
