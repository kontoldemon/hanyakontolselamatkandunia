import StatusPage from "@/components/StatusPage";

export default function NotFound() {
  return (
    <StatusPage
      code="404"
      title="Page not found"
      message="Requested dashboard route does not exist or was moved."
      secondaryAction="back"
    />
  );
}
