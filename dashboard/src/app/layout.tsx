
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Sidebar from "@/components/Sidebar";
import { ThemeProvider } from "@/components/theme-provider";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "CloudSentinel",
  description: "Enterprise SSH Threat Detection System",
  icons: {
    icon: "/logo.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={inter.className}>
        <ThemeProvider
          attribute="class"
          defaultTheme="dark"
          enableSystem
          disableTransitionOnChange
        >
          <div className="flex flex-col md:flex-row min-h-screen bg-slate-50 dark:bg-[#050505] text-slate-900 dark:text-slate-100 transition-colors duration-300 antialiased selection:bg-blue-500/30">
            {/* Sidebar (Desktop) */}
            <Sidebar />

            {/* Main Content */}
            <main className="flex-1 min-w-0 p-4 md:p-6 xl:p-8 bg-slate-50 dark:bg-[#050505]">
              {children}
            </main>
          </div>
        </ThemeProvider>
      </body>
    </html>
  );
}
