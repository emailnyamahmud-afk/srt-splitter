import type { NextConfig } from "next";

// For GitHub Pages project sites (https://USERNAME.github.io/REPO_NAME/),
// basePath is automatically set to "/REPO_NAME" when building under GitHub Actions.
// For root domain or local dev, basePath stays empty.
const repoName =
  process.env.GITHUB_REPOSITORY?.split("/")[1] ?? "";
const isGHPages = process.env.GITHUB_ACTIONS === "true" && !!repoName;

const nextConfig: NextConfig = {
  // Static export: build produces a fully static site under ./out
  // that can be opened with any static server (e.g. `bunx serve out`)
  // or even file:// in most browsers.
  output: "export",
  basePath: isGHPages ? `/${repoName}` : "",
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
