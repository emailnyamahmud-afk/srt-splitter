import type { NextConfig } from "next";

const isVercel = process.env.VERCEL === "1";
const repoName =
  process.env.GITHUB_REPOSITORY?.split("/")[1] ?? "";
const isGHPages = process.env.GITHUB_ACTIONS === "true" && !!repoName;

const nextConfig: NextConfig = {
  // On Vercel: keep default (no output: export) so /api/* routes work as functions.
  // On GitHub Pages: use static export (no backend possible).
  output: isVercel ? undefined : "export",
  basePath: isGHPages ? `/${repoName}` : "",
  images: { unoptimized: true },
  trailingSlash: true,
  typescript: { ignoreBuildErrors: true },
  reactStrictMode: false,
};

export default nextConfig;
