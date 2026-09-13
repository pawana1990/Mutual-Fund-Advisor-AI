import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Wealth Advisor",
  description: "Evidence-first AI portfolio intelligence for mutual fund investors.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
