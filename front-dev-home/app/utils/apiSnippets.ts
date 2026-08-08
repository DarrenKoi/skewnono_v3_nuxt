// Copy-paste snippet builders for the API reference page.
//
// Pure string formatting over an `ApiEndpoint`, so it lives next to the other
// export/format utils rather than inside the page that renders it.

import type { ApiEndpoint, ApiMethod } from '~/data/apiCatalog'

export const methodColor = (method: ApiMethod): 'primary' | 'success' | 'error' => {
  if (method === 'POST') return 'success'
  if (method === 'DELETE') return 'error'
  return 'primary'
}

export const toQueryString = (query?: Record<string, string>): string => {
  if (!query) return ''
  const parts = Object.entries(query).map(([key, value]) => `${key}=${value}`)
  return parts.length ? `?${parts.join('&')}` : ''
}

export const curlExample = (endpoint: ApiEndpoint): string => {
  const url = `$BASE_URL${endpoint.example.path}${toQueryString(endpoint.example.query)}`
  if (endpoint.method === 'POST') {
    return `curl -X POST \\
  -H "Authorization: Bearer $SKEWNONO_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '${JSON.stringify(endpoint.example.body)}' \\
  "${url}"`
  }
  if (endpoint.method === 'DELETE') {
    return `curl -X DELETE -H "Authorization: Bearer $SKEWNONO_TOKEN" \\
  "${url}"`
  }
  return `curl -H "Authorization: Bearer $SKEWNONO_TOKEN" \\
  "${url}"`
}

export const pythonExample = (endpoint: ApiEndpoint): string => {
  const lines = [
    `resp = requests.${endpoint.method.toLowerCase()}(`,
    `    f"{BASE_URL}${endpoint.example.path}",`,
    '    headers=HEADERS,'
  ]
  if (endpoint.example.query) {
    lines.push(`    params=${JSON.stringify(endpoint.example.query)},`)
  }
  if (endpoint.example.body !== undefined) {
    lines.push(`    json=${JSON.stringify(endpoint.example.body)},`)
  }
  lines.push('    timeout=10,', ')', 'resp.raise_for_status()', 'data = resp.json()')
  return lines.join('\n')
}
