export const escapeCsvValue = (value: unknown): string => {
  const normalized = String(value ?? '').replace(/"/g, '""')
  return `"${normalized}"`
}

// Compose CSV text (no BOM): header + rows, every value escaped, CRLF-joined.
// Pure — safe to import and call under `node --test`.
export const buildCsvContent = (headers: string[], rows: unknown[][]): string => {
  const headerRow = headers.map(escapeCsvValue).join(',')
  const bodyRows = rows.map(row => row.map(escapeCsvValue).join(','))
  return [headerRow, ...bodyRows].join('\r\n')
}

// Hand a Blob to the browser as a download. The object-URL dance is fiddly and
// easy to get subtly wrong (a missing revoke leaks the blob for the life of the
// document), so it lives here once rather than in each exporter. Client-only.
export const downloadBlob = (filename: string, blob: Blob): void => {
  if (!import.meta.client) return

  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

// Download an arbitrary CSV string. Excel reads UTF-8 only when a BOM (U+FEFF)
// is present, so this is the single place the BOM is added. Client-only.
export const downloadCsvRaw = (filename: string, content: string): void => {
  if (!import.meta.client || content.length === 0) return

  downloadBlob(filename, new Blob(['﻿' + content], { type: 'text/csv;charset=utf-8;' }))
}

export const downloadCsv = (
  filename: string,
  headers: string[],
  rows: unknown[][]
): void => {
  if (rows.length === 0) return
  downloadCsvRaw(filename, buildCsvContent(headers, rows))
}

// Copy plain text with the same fallback used by table exports. Clipboard API
// access can be unavailable outside HTTPS/localhost, so keep the legacy path
// for office deployments that still run over an internal HTTP address.
export const copyTextToClipboard = async (text: string): Promise<boolean> => {
  if (!import.meta.client) return false

  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text)
      return true
    } catch {
      // Fall through to the execCommand fallback (e.g. http:// production).
    }
  }

  try {
    const textarea = document.createElement('textarea')
    textarea.value = text
    textarea.style.position = 'fixed'
    textarea.style.top = '-9999px'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.focus()
    textarea.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(textarea)
    return ok
  } catch {
    return false
  }
}

// Copy a table to the clipboard as TSV (tab-separated). Excel, Google
// Sheets, and other spreadsheets split pasted text on tabs, so TSV pastes
// straight into cells with no import step. Tabs/newlines inside a value are
// flattened to spaces so a stray value can't break the row/column grid.
// Returns true on success so callers can show a confirmation toast.
export const copyTableToClipboard = async (
  headers: string[],
  rows: unknown[][]
): Promise<boolean> => {
  if (!import.meta.client || rows.length === 0) return false

  const toCell = (value: unknown): string =>
    String(value ?? '').replace(/[\t\r\n]+/g, ' ')
  const tsv = [headers, ...rows]
    .map(row => row.map(toCell).join('\t'))
    .join('\r\n')

  return copyTextToClipboard(tsv)
}
