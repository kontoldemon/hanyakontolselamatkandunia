"use client";

import StatusPage from "@/components/ui/StatusPage";

export default function ErrorPage({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <StatusPage
      code="500"
      title="Dashboard error"
      message="Interface encountered an unexpected error while loading this view. Retry, or return to the main dashboard."
      primaryLabel="Dashboard"
      secondaryAction="reload"
      onRetry={reset}
    />
  );
}
