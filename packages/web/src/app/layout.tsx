import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "DEFENDER AI — Public Defender Assistant",
  description: "AI-powered multi-agent system for public defenders",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
