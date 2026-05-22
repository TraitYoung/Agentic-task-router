import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SpecForge — AI Software Engineering Spec Generator",
  description: "将想法或代码转化为可交付的软件工程规格、测试计划与 Cursor 就绪的 Prompts。",
  icons: { icon: "/favicon.svg" },
  openGraph: {
    title: "SpecForge — AI Software Engineering Spec Generator",
    description: "Multi-Agent + RAG powered spec generation and code review.",
  },
};

export const viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
