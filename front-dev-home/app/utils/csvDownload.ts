export const escapeCsvValue = (value: unknown): string => {
  const normalized = String(value ?? '').replace(/"/g, '""')
  return `"${normalized}"`
}

// Excel reads UTF-8 only when a BOM (U+FEFF) is present and CRLF line
// endings are used; without these, Korean/Japanese values render as
// mojibake on Windows.
export const downloadCsv = (
  filename: string,
  headers: string[],
  rows: unknown[][]
): void => {
  if (!import.meta.client || rows.length === 0) return

  const headerRow = headers.map(escapeCsvValue).join(',')
  const bodyRows = rows.map(row => row.map(escapeCsvValue).join(','))
  const csvContent = ['﻿' + headerRow, ...bodyRows].join('\r\n')

  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
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
