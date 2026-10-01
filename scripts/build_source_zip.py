#!/usr/bin/env python3
"""Package source-code into a ZIP for offline distribution.
Excludes node_modules, .next, out, .git, .zscripts, dev.log, etc.
"""
import zipfile
import os
from pathlib import Path

PROJECT_ROOT = Path("/home/z/my-project")
OUTPUT_ZIP = Path("/home/z/my-project/download/srt-splitter-source.zip")

EXCLUDE_DIRS = {
    "node_modules",
    ".next",
    ".git",
    ".zscripts",
    "out",
    "download",
    "upload",
    "tests",
    "examples",
    "mini-services",
    "prisma",
    "skills",      # internal skill defs, not part of user app
    "agent-ctx",    # if any
    "db",           # local dev database, no need to ship
}

EXCLUDE_FILES = {
    "dev.log",
    "server.log",
    ".env",
    ".DS_Store",
    "bun.lock",
}

INCLUDE_EXTRAS = {
    PROJECT_ROOT / "SOURCE_README.md": "README.md",
}

# GitHub Actions workflow file
WORKFLOW_CONTENT = """name: Deploy to GitHub Pages

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: "pages"
  cancel-in-progress: true

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: oven-sh/setup-bun@v2
        with:
          bun-version: latest
      - run: bun install
      - run: bun run build
      - uses: actions/upload-pages-artifact@v3
        with:
          path: ./out

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
"""

# next.config with basePath placeholder for GitHub Pages
NEXT_CONFIG_GH = '''import type { NextConfig } from "next";

// For GitHub Pages project sites (https://USERNAME.github.io/REPO_NAME/),
// set basePath to "/REPO_NAME". For root domain or local dev, leave it empty.
const repoName = process.env.GITHUB_REPOSITORY?.split("/")[1] ?? "";
const isGHPages = process.env.GITHUB_ACTIONS === "true" && repoName;

const nextConfig: NextConfig = {
  output: "export",
  basePath: isGHPages ? `/${repoName}` : "",
  images: { unoptimized: true },
  trailingSlash: true,
  typescript: { ignoreBuildErrors: true },
  reactStrictMode: false,
};

export default nextConfig;
'''


def should_skip_dir(dirpath: Path) -> bool:
    name = dirpath.name
    if name in EXCLUDE_DIRS:
        return True
    if name.startswith("."):
        # Allow .github
        if name == ".github":
            return False
        return True
    return False


def should_skip_file(filepath: Path) -> bool:
    if filepath.name in EXCLUDE_FILES:
        return True
    # Skip binary/large files we don't want
    if filepath.suffix.lower() in {".log", ".pid", ".tar", ".zip"}:
        return True
    return False


def main():
    OUTPUT_ZIP.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT_ZIP.exists():
        OUTPUT_ZIP.unlink()

    FIXED_TIMESTAMP = (2024, 1, 1, 0, 0, 0)

    def add_file(zf, fpath, arcname):
        """Add file with a fixed (1980+) timestamp to avoid ZIP epoch issue."""
        with open(fpath, "rb") as f:
            data = f.read()
        zi = zipfile.ZipInfo(arcname, FIXED_TIMESTAMP)
        zi.compress_type = zipfile.ZIP_DEFLATED
        zi.external_attr = 0o644 << 16
        zf.writestr(zi, data)

    def add_str(zf, content, arcname):
        zi = zipfile.ZipInfo(arcname, FIXED_TIMESTAMP)
        zi.compress_type = zipfile.ZIP_DEFLATED
        zi.external_attr = 0o644 << 16
        zf.writestr(zi, content)

    # These files we replace with custom versions in add_extras below,
    # so skip the original copies when walking.
    SKIP_WALK_FILES = {
        "next.config.ts",
        "SOURCE_README.md",
        ".gitignore",  # we write our own below
    }

    def add_extras(zf):
        # Add README as source README
        for src, dst in INCLUDE_EXTRAS.items():
            if src.exists():
                add_file(zf, src, dst)
        # Add GitHub Actions workflow
        add_str(zf, WORKFLOW_CONTENT, ".github/workflows/deploy.yml")
        # Replace next.config.ts with GitHub Pages-aware version
        add_str(zf, NEXT_CONFIG_GH, "next.config.ts")
        # Add .gitignore
        add_str(zf, "\n".join([
            "node_modules/",
            ".next/",
            "out/",
            "*.log",
            ".env",
            ".DS_Store",
            "",
        ]), ".gitignore")

    with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        # Walk source tree
        for root, dirs, files in os.walk(PROJECT_ROOT):
            root_path = Path(root)
            dirs[:] = [d for d in dirs if not should_skip_dir(root_path / d)]
            for fname in files:
                if fname in SKIP_WALK_FILES:
                    continue
                fpath = root_path / fname
                if should_skip_file(fpath):
                    continue
                arcname = fpath.relative_to(PROJECT_ROOT)
                parts = arcname.parts
                if "upload" in parts or "download" in parts or "out" in parts:
                    continue
                add_file(zf, fpath, str(arcname))

        add_extras(zf)

    size = OUTPUT_ZIP.stat().st_size
    print(f"Created {OUTPUT_ZIP} ({size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
