import StatusPage from "@/components/StatusPage";

export default function OfflinePage() {
  return (
    <StatusPage
      code="OFFLINE"
      title="Sensor offline"
      message="CloudSentinel dashboard is reachable, but live sensor services are not responding yet."
      primaryLabel="Dashboard"
      secondaryAction="reload"
    />
  );
}
