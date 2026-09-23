import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Enterprise Knowledge Graph & RAG",
  description: "Agentic Enterprise Knowledge Graph & Multi-Source RAG Pipeline",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-canvas antialiased">{children}</body>
    </html>
  );
}
