import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Static export: build produces a fully static site under ./out
  // that can be opened with any static server (e.g. `bunx serve out`)
  // or even file:// in most browsers.
  output: "export",
  // App Router already supports this. Disable image optimization since
  // static export cannot use the server-side image optimizer.
  images: {
    unoptimized: true,
  },
  // Produce flat HTML in case the user opens via file://
  trailingSlash: true,
  typescript: {
    ignoreBuildErrors: true,
  },
  reactStrictMode: false,
};

export default nextConfig;
