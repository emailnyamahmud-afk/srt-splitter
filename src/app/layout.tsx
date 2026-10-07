import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as SonnerToaster } from "@/components/ui/sonner";
import { CoiServiceworkerScript } from "@/components/coi-script";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "SRT Splitter — Dubbing Studio",
  description: "Split SRT, translate, dubbing dengan TTS. Editor SRT Jawa dengan ngoko/krama. 100% sync video.",
  keywords: ["SRT", "subtitle", "split", "dubbing", "TTS", "Jawa", "ngoko", "krama", "Indonesia"],
  authors: [{ name: "SRT Splitter" }],
  icons: {
    icon: "/logo.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        {/* coi-serviceworker enables cross-origin isolation (SharedArrayBuffer)
            which is required by Transformers.js for multi-threaded WASM.
            Without it, TTS model would run single-threaded (very slow). */}
        <CoiServiceworkerScript />
      </head>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-background text-foreground`}
      >
        {children}
        <Toaster />
        <SonnerToaster position="top-center" richColors closeButton />
      </body>
    </html>
  );
}
