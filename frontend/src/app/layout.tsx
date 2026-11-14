import "./globals.css";
import React from "react";
import { Geist, Geist_Pixel, Instrument_Serif } from "next/font/google";

// Fonts matching the RiceApps site
const geist = Geist({ subsets: ["latin"], variable: "--font-geist" });
const pixel = Geist_Pixel({ subsets: ["latin"], variable: "--font-pixel" });
const serif = Instrument_Serif({ subsets: ["latin"], weight: "400", style: "italic", variable: "--font-serif" });

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${geist.variable} ${pixel.variable} ${serif.variable}`}>
      <body className="dot-grid min-h-screen bg-neutral-100 font-(family-name:--font-geist) text-neutral-900">
        {children}
      </body>
    </html>
  );
}
