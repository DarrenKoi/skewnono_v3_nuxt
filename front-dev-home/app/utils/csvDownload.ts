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
