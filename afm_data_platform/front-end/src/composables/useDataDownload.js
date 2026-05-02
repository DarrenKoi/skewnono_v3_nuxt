import { computed } from 'vue'
import { downloadCSV, formatMeasurementInfo, formatSummaryStatistics, formatProfileData, generateFilename } from '@/utils/exportUtils.js'

/**
 * Composable for handling data downloads in ResultPage
 */
export function useDataDownload(measurementInfo, summaryData, detailedData, profileData, selectedPoint) {
  // Check if we have any data to download
  const hasData = computed(() => {
    return (measurementInfo.value && Object.keys(measurementInfo.value).length > 0) ||
           (summaryData.value && summaryData.value.length > 0) ||
           (detailedData.value && detailedData.value.length > 0)
  })

  // Download measurement info
  function downloadMeasurementInfo() {
    const data = formatMeasurementInfo(measurementInfo.value)
    const filename = generateFilename('measurement_info', measurementInfo.value)
    downloadCSV(data, filename)
  }

  // Download summary statistics
  function downloadSummaryStatistics() {
    const data = formatSummaryStatistics(summaryData.value)
    const filename = generateFilename('summary_statistics', measurementInfo.value)
    downloadCSV(data, filename)
  }

  // Download detailed data
  function downloadDetailedData() {
    const filename = generateFilename('detailed_data', measurementInfo.value)
    downloadCSV(detailedData.value, filename)
  }

  // Download profile data
  function downloadProfileData() {
    const data = formatProfileData(profileData.value)
    const filename = generateFilename(`profile_data_point_${selectedPoint.value || 'all'}`, measurementInfo.value)
    downloadCSV(data, filename)
  }

  // Download all data
  function downloadAllData() {
    // Create a combined dataset
    const timestamp = new Date().toISOString().split('T')[0].replace(/-/g, '')
    const lotId = measurementInfo.value.lot_id || 'unknown'
    const recipe = measurementInfo.value.recipe_name || 'data'

    // Download each dataset separately with related names
    const baseFilename = `AFM_${recipe}_${lotId}_${timestamp}`

    // Download measurement info
    if (measurementInfo.value && Object.keys(measurementInfo.value).length > 0) {
      const infoData = formatMeasurementInfo(measurementInfo.value)
      downloadCSV(infoData, `${baseFilename}_info`)
    }

    // Download summary statistics
    if (summaryData.value && summaryData.value.length > 0) {
      const summaryFormatted = formatSummaryStatistics(summaryData.value)
      downloadCSV(summaryFormatted, `${baseFilename}_summary`)
    }

    // Download detailed data
    if (detailedData.value && detailedData.value.length > 0) {
      downloadCSV(detailedData.value, `${baseFilename}_detailed`)
    }

    // Download profile data if available
    if (profileData.value && profileData.value.length > 0) {
      const profileFormatted = formatProfileData(profileData.value)
      downloadCSV(profileFormatted, `${baseFilename}_profile_point_${selectedPoint.value || 'last'}`)
    }
  }

  return {
    hasData,
    downloadMeasurementInfo,
    downloadSummaryStatistics,
    downloadDetailedData,
    downloadProfileData,
    downloadAllData
  }
}