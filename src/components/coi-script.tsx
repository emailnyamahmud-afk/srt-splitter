'use client'

/**
 * Injects the coi-serviceworker.js script into the document head.
 * This service worker enables cross-origin isolation (SharedArrayBuffer)
 * required by Transformers.js for multi-threaded WASM execution.
 *
 * Without this, TTS would run single-threaded and 4-10x slower.
 * The script must run early, before any WASM modules are loaded.
 */
export function CoiServiceworkerScript() {
  return (
    <script
      // Important: must NOT have type="module" so it executes sync
      src="/coi-serviceworker.js"
      // No async — load this before the app boots
      defer={false}
    />
  )
}
