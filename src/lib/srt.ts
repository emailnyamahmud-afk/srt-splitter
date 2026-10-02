// SRT parsing and splitting utilities — all client-side, no backend needed.

export interface SrtEntry {
  start: number; // seconds (float)
  end: number; // seconds (float)
  textLines: string[];
}

export interface SrtPart {
  index: number; // 1-based
  entries: SrtEntry[];
  startSec: number; // original timeline start (seconds)
  endSec: number; // original timeline end (seconds)
  durationSec: number;
  entryCount: number;
}

export interface SplitResult {
  totalEntries: number;
  totalDurationSec: number;
  parts: SrtPart[];
}

/**
 * Parse "HH:MM:SS,mmm" → seconds (float)
 */
export function parseTime(ts: string): number {
  // Tolerate "." decimal separator too (some VTT)
  const normalized = ts.replace(".", ",");
  const [hms, ms = "0"] = normalized.split(",");
  const [h, m, s] = hms.split(":").map(Number);
  return h * 3600 + m * 60 + s + Number(ms) / 1000;
}

/**
 * Format seconds (float) → "HH:MM:SS,mmm"
 */
export function formatTime(seconds: number): string {
  if (seconds < 0) seconds = 0;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  let ms = Math.round((seconds - Math.floor(seconds)) * 1000);
  if (ms === 1000) {
    ms = 0;
    // We could carry-over but it's an edge case rarely hit in practice.
  }
  return `${pad(h, 2)}:${pad(m, 2)}:${pad(s, 2)},${pad(ms, 3)}`;
}

function pad(n: number, len: number): string {
  return String(n).padStart(len, "0");
}

const TIME_RANGE_RE =
  /(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})/;

/**
 * Parse a full SRT file content into a list of entries.
 * Robust to BOM, \r\n, blank lines, missing index line.
 */
export function parseSrt(content: string): SrtEntry[] {
  const normalized = content.replace(/\r\n/g, "\n").replace(/\r/g, "\n").trim();
  if (!normalized) return [];

  const blocks = normalized.split(/\n\s*\n/);
  const entries: SrtEntry[] = [];

  for (const block of blocks) {
    const lines = block.split("\n").filter((l) => l.trim() !== "");
    if (lines.length < 1) continue;

    // Find the line containing "-->"
    let timeLineIdx = -1;
    for (let i = 0; i < lines.length; i++) {
      if (TIME_RANGE_RE.test(lines[i])) {
        timeLineIdx = i;
        break;
      }
    }
    if (timeLineIdx === -1) continue;

    const match = lines[timeLineIdx].match(TIME_RANGE_RE);
    if (!match) continue;
    const start = parseTime(match[1]);
    const end = parseTime(match[2]);
    const textLines = lines.slice(timeLineIdx + 1);
    entries.push({ start, end, textLines });
  }

  return entries;
}

export interface SplitOptions {
  maxMinutes: number;
  prefix: string;
  resetTimestamps: boolean;
  splitOnBoundary: boolean;
  splitByChars?: number;
}

/**
 * Split entries into parts, each with max duration = maxMinutes.
 * Splitting happens at subtitle boundaries (we don't cut mid-subtitle),
 * so actual part durations will be ≤ maxMinutes (or slightly over only if a single
 * subtitle itself exceeds maxMinutes, which is rare).
 */
export function splitEntries(
  entries: SrtEntry[],
  opts: SplitOptions,
): SplitResult {
  if (entries.length === 0) {
    return { totalEntries: 0, totalDurationSec: 0, parts: [] };
  }
  const totalDurationSec = entries[entries.length - 1].end;

  // Mode: split by character count
  if (opts.splitByChars && opts.splitByChars > 0) {
    return splitByCharCount(entries, opts.splitByChars);
  }

  // Mode: split by duration (default)
  const maxSeconds = opts.maxMinutes * 60;
  const parts: SrtPart[] = [];
  let currentEntries: SrtEntry[] = [];
  let partStartSec = 0;
  let nextBoundary = maxSeconds;
  let partIdx = 1;

  for (const entry of entries) {
    if (currentEntries.length > 0 && entry.start >= nextBoundary) {
      parts.push(buildPart(partIdx, currentEntries, partStartSec));
      partIdx++;
      partStartSec = nextBoundary;
      nextBoundary += maxSeconds;
      currentEntries = [];
    }
    currentEntries.push(entry);
  }
  if (currentEntries.length > 0) {
    parts.push(buildPart(partIdx, currentEntries, partStartSec));
  }

  return {
    totalEntries: entries.length,
    totalDurationSec,
    parts,
  };
}

function splitByCharCount(
  entries: SrtEntry[],
  maxChars: number,
): SplitResult {
  const totalDurationSec = entries[entries.length - 1].end;
  const parts: SrtPart[] = [];
  let currentEntries: SrtEntry[] = [];
  let currentChars = 0;
  let partIdx = 1;

  for (const entry of entries) {
    const entryChars = entry.textLines.join(' ').length;
    if (currentEntries.length > 0 && currentChars + entryChars > maxChars) {
      parts.push(buildPart(partIdx, currentEntries, 0));
      partIdx++;
      currentEntries = [];
      currentChars = 0;
    }
    currentEntries.push(entry);
    currentChars += entryChars;
  }
  if (currentEntries.length > 0) {
    parts.push(buildPart(partIdx, currentEntries, 0));
  }
  return { totalEntries: entries.length, totalDurationSec, parts };
}

function buildPart(
  index: number,
  entries: SrtEntry[],
  partStartSec: number,
): SrtPart {
  const startSec = entries[0].start;
  const endSec = entries[entries.length - 1].end;
  return {
    index,
    entries,
    startSec,
    endSec,
    durationSec: endSec - partStartSec,
    entryCount: entries.length,
  };
}

/**
 * Serialize a part back into SRT text.
 * If resetTimestamps is true, the first entry starts at 00:00:00,000.
 * Otherwise, original timestamps are kept.
 */
export function serializePart(
  part: SrtPart,
  resetTimestamps: boolean,
): string {
  const offset = resetTimestamps ? part.startSec : 0;
  let out = "";
  part.entries.forEach((entry, i) => {
    const start = entry.start - offset;
    const end = entry.end - offset;
    out += `${i + 1}\n`;
    out += `${formatTime(start)} --> ${formatTime(end)}\n`;
    for (const line of entry.textLines) out += line + "\n";
    out += "\n";
  });
  return out;
}

/**
 * Trigger a browser download for a text file.
 */
export function downloadTextFile(
  filename: string,
  content: string,
  mime = "application/x-subrip;charset=utf-8",
) {
  const blob = new Blob([content], { type: mime });
  triggerBlobDownload(filename, blob);
}

/**
 * Trigger a browser download from a Blob.
 */
export function triggerBlobDownload(filename: string, blob: Blob) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/**
 * Build a single ZIP file containing all SRT parts and trigger a download.
 * Uses JSZip to bundle everything into one .zip archive in the browser.
 */
export async function downloadAllPartsAsZip(
  parts: SrtPart[],
  prefix: string,
  resetTimestamps: boolean,
  zipName?: string,
) {
  // Lazy import to keep initial bundle smaller
  const JSZip = (await import("jszip")).default;
  const zip = new JSZip();

  for (const part of parts) {
    const filename = `${prefix}-${String(part.index).padStart(2, "0")}.srt`;
    const content = serializePart(part, resetTimestamps);
    zip.file(filename, content);
  }

  // Add a small index file summarizing the parts
  const indexLines: string[] = [
    `${prefix}-split.txt`,
    "",
    `Total parts: ${parts.length}`,
    "",
    "File | Start | End | Duration | Entries",
    "-----|-------|-----|----------|--------",
  ];
  for (const part of parts) {
    indexLines.push(
      [
        `${prefix}-${String(part.index).padStart(2, "0")}.srt`,
        formatTime(part.startSec),
        formatTime(part.endSec),
        formatTime(part.durationSec),
        String(part.entryCount),
      ].join(" | "),
    );
  }
  zip.file(`${prefix}-split.txt`, indexLines.join("\n"));

  const blob = await zip.generateAsync({
    type: "blob",
    compression: "DEFLATE",
    compressionOptions: { level: 6 },
  });

  const finalName = zipName ?? `${prefix}-split.zip`;
  triggerBlobDownload(finalName, blob);
}
