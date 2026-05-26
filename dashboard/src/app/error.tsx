"use client";

import StatusPage from "@/components/StatusPage";

export default function ErrorPage() {
  return (
    <StatusPage
      code="500"
      title="Dashboard error"
      message="Interface failed while loading this view. Retry, then check deployment logs if it keeps happening."
      primaryLabel="Dashboard"
      secondaryAction="reload"
    />
  );
}
