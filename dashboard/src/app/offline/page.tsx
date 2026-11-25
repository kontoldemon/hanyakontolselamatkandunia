import type { Metadata } from "next";
import { WifiOff } from "lucide-react";
import StatusPage from "@/components/ui/StatusPage";

export const metadata: Metadata = {
  title: "CloudSentinel \u2022 Offline",
  icons: {
    icon: "/logo-grey.svg",
  },
};

export default function OfflinePage() {
  return (
    <StatusPage
      icon={<WifiOff size={28} className="text-rose-500 drop-shadow-[0_0_8px_rgba(244,63,94,0.4)]" strokeWidth={2.2} />}
      title="No connection"
      message="You appear to be offline. Reconnect to internet or VPN and retry."
      primaryHref="/"
      primaryLabel="Dashboard"
      secondaryAction="reload"
    />
  );
}
