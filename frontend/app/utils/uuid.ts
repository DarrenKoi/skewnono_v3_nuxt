/**
 * Canonical lowercase UUID v4, usable outside secure contexts.
 *
 * `crypto.randomUUID` does not exist on plain-HTTP origins (only `randomUUID`
 * and `subtle` are secure-context gated), and the Phase 3 cloud is served over
 * http://. `crypto.getRandomValues` is available everywhere, so the fallback
 * assembles the same RFC 4122 shape the backend's canonical-UUID validation
 * (`str(UUID(v)) == v`) requires.
 */
export function generateUuid(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  const bytes = new Uint8Array(16)
  crypto.getRandomValues(bytes)
  bytes[6] = (bytes[6]! & 0x0f) | 0x40
  bytes[8] = (bytes[8]! & 0x3f) | 0x80
  const hex = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('')
  return [
    hex.slice(0, 8),
    hex.slice(8, 12),
    hex.slice(12, 16),
    hex.slice(16, 20),
    hex.slice(20)
  ].join('-')
}
