import StatusPage from "@/components/ui/StatusPage";

export default function NotFoundPage() {
  return (
    <StatusPage
      code="404"
      title="Page not found"
      message="The requested route does not exist or has been moved."
      primaryHref="/dashboard"
      primaryLabel="Dashboard"
      secondaryAction="back"
    />
  );
}
