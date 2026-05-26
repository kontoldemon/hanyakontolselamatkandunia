import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CloudSentinel War Room",
  description: "CloudSentinel Phase 1 threat operations dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
