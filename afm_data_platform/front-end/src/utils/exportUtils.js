// Utility functions for exporting data to CSV format

/**
 * Convert array of objects to CSV string
 * @param {Array} data - Array of objects to convert
 * @param {Array} headers - Optional array of header names to use (in order)
 * @returns {String} CSV formatted string
 */
export function arrayToCSV(data, headers = null) {
  if (!data || data.length === 0) {
    return ''
  }

  // Get headers from the first object if not provided
  const allHeaders = headers || Object.keys(data[0])
  
  // Create header row
  const headerRow = allHeaders.map(header => `"${header}"`).join(',')
  
  // Create data rows
  const dataRows = data.map(row => {
    return allHeaders.map(header => {
      const value = row[header]
      
      // Handle different value types
      if (value === null || value === undefined) {
        return ''
      }
      
      // Convert to string and escape quotes
      const stringValue = String(value).replace(/"/g, '""')
      
      // Wrap in quotes if contains comma, newline, or quotes
      if (stringValue.includes(',') || stringValue.includes('\n') || stringValue.includes('"')) {
        return `"${stringValue}"`
      }
      
      return stringValue
    }).join(',')
  })
  
  // Combine header and data rows
  return [headerRow, ...dataRows].join('\n')
}

/**
 * Download data as CSV file
 * @param {Array} data - Array of objects to download
 * @param {String} filename - Name of the file to download
 * @param {Array} headers - Optional array of header names to use (in order)
 */
export function downloadCSV(data, filename, headers = null) {
  const csv = arrayToCSV(data, headers)
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  
  const link = document.createElement('a')
  link.href = url
  link.download = filename.endsWith('.csv') ? filename : `${filename}.csv`
  
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  
  // Clean up the URL object
  URL.revokeObjectURL(url)
}

/**
 * Convert measurement info object to downloadable format
 * @param {Object} info - Measurement info object
 * @returns {Array} Array with single object for CSV export
 */
export function formatMeasurementInfo(info) {
  if (!info || typeof info !== 'object') {
    return []
  }
  
  // Convert object to array with single row
  return [info]
}

/**
 * Format summary statistics for export
 * @param {Array} summaryData - Summary statistics data
 * @returns {Array} Formatted array for CSV export
 */
export function formatSummaryStatistics(summaryData) {
  if (!summaryData || !Array.isArray(summaryData)) {
    return []
  }
  
  // Return as-is since it's already in the right format
  return summaryData
}

/**
 * Format profile data for export
 * @param {Array} profileData - Profile coordinate data
 * @returns {Array} Formatted array for CSV export
 */
export function formatProfileData(profileData) {
  if (!profileData || !Array.isArray(profileData)) {
    return []
  }
  
  // Ensure consistent decimal places for coordinates
  return profileData.map(point => ({
    x: Number(point.x).toFixed(6),
    y: Number(point.y).toFixed(6),
    z: Number(point.z).toFixed(6)
  }))
}

/**
 * Create a combined dataset from multiple data sources
 * @param {Object} measurementInfo - Basic measurement information
 * @param {Array} summaryData - Summary statistics
 * @param {Array} detailedData - Detailed measurement data
 * @returns {Object} Object containing separate sheets of data
 */
export function createCombinedDataset(measurementInfo, summaryData, detailedData) {
  return {
    'Measurement Info': formatMeasurementInfo(measurementInfo),
    'Summary Statistics': formatSummaryStatistics(summaryData),
    'Detailed Data': detailedData || []
  }
}

/**
 * Generate filename with timestamp
 * @param {String} prefix - Filename prefix
 * @param {Object} measurementInfo - Measurement info for context
 * @returns {String} Formatted filename
 */
export function generateFilename(prefix, measurementInfo = {}) {
  const timestamp = new Date().toISOString().split('T')[0].replace(/-/g, '')
  const lotId = measurementInfo.lot_id || 'unknown'
  const recipe = measurementInfo.recipe_name || 'data'
  
  return `${prefix}_${recipe}_${lotId}_${timestamp}`
}