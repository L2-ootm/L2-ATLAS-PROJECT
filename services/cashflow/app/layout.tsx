import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import Sidebar from "@/components/Sidebar";
import NeuralCommandOverlay from "@/components/NeuralCommandOverlay";
import TopoField from "@/components/TopoField";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const jetbrains = JetBrains_Mono({ subsets: ["latin"], variable: "--font-jetbrains" });

export const metadata: Metadata = {
  title: "ATLAS // Cashflow",
  description: "Gestão financeira completa — módulo ATLAS, L2 Systems",
  manifest: "/manifest.json",
  appleWebApp: { capable: true, statusBarStyle: "black-translucent", title: "ATLAS Cashflow" },
};

export const viewport: Viewport = {
  themeColor: "#0B0D12",
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
        <div className="topo-field" style={{ minHeight: "100vh" }}>
          {/* Living terrain — SVG contour engine; the static CSS lattice is
              retired in its favor (the engine draws its own resting field). */}
          <TopoField />
          <div className="app-shell">
            <Sidebar />
            <main className="app-main">
              {children}
            </main>
          </div>
        </div>
        <NeuralCommandOverlay />
      </body>
    </html>
  );
}
