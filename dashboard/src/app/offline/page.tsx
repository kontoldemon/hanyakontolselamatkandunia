import type { Metadata } from "next";
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
      code="OFFLINE"
      title="No connection"
      message="You are currently offline. Check your internet connection or VPN and retry."
      primaryHref="/"
      primaryLabel="Dashboard"
      secondaryAction="reload"
    />
  );
}
