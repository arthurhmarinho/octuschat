import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "InboxPilot — automação de DMs do Instagram",
  description:
    "Conecte seu Instagram e dispare DMs automáticas quando alguém comentar ou usar uma palavra-chave.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="pt-BR">
      <body>
        <div className="grid-bg" />
        {children}
      </body>
    </html>
  );
}
