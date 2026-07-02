import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import Sidebar from "@/components/Sidebar";
import NeuralCommandOverlay from "@/components/NeuralCommandOverlay";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const jetbrains = JetBrains_Mono({ subsets: ["latin"], variable: "--font-jetbrains" });

export const metadata: Metadata = {
  title: "L2 Financeiro",
  description: "Gestão financeira — L2 Systems",
  manifest: "/manifest.json",
  appleWebApp: { capable: true, statusBarStyle: "black-translucent", title: "L2 Financeiro" },
};

export const viewport: Viewport = {
  themeColor: "#050816",
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="pt-BR">
      <head>
        <link rel="apple-touch-icon" href="/icon-192.png" />
      </head>
      <body
        suppressHydrationWarning
        className={`${inter.variable} ${jetbrains.variable} antialiased`}
      >
        <div className="topo-field topo-lattice" style={{ minHeight: "100vh" }}>
          <div style={{ display: "flex", minHeight: "100vh" }}>
            <Sidebar />
            <main style={{ flex: 1, padding: "32px", minWidth: 0 }}>
              {children}
            </main>
          </div>
        </div>
        <NeuralCommandOverlay />
      </body>
    </html>
  );
}
