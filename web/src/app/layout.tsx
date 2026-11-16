import type { Metadata, Viewport } from "next";
import "./fonts";
import "./globals.css";
import { EffectsProvider } from "@/lib/effects";

export const metadata: Metadata = {
  title: "ShaOn Voice AI",
  description: "Configurable multilingual voice agents: Bengali, Hindi, Kannada, Japanese, English.",
};
export const viewport: Viewport = { themeColor: "#06070b", width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 btn">Skip to content</a>
        <EffectsProvider>{children}</EffectsProvider>
      </body>
    </html>
  );
}
