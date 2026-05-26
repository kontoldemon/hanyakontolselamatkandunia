import StatusPage from "@/components/StatusPage";

export default function HttpVersionPage() {
  return (
    <StatusPage
      code="505"
      title="Request not supported"
      message="This endpoint expects a normal HTTPS browser request. Try dashboard home or reload after network changes."
      primaryLabel="Dashboard"
      secondaryAction="reload"
    />
  );
}
