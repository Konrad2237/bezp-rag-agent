import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "BEZ PIERDOLENIA — AI Trener Personalny",
  description: "AI trener personalny oparty na RAG i agentach",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="pl" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
