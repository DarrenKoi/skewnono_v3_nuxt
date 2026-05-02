import { afmService } from './afmService'

/**
 * Data Processing Service
 * Handles data transformation and processing functions
 */

// Local search function - filters pre-loaded data instead of making API calls
export function filterMeasurementsLocally(allData, query) {
  try {
    console.log(`🔍 FilterMeasurementsLocally called with query: "${query}" on ${allData.length} items`)
    
    if (!query || query.trim() === '' || query.trim().length < 2) {
      // Return all data sorted by date (latest first)
      const sortedData = [...allData].sort((a, b) => {
        const dateA = new Date(a.formatted_date)
        const dateB = new Date(b.formatted_date)
        return dateB - dateA
      })
      console.log(`✅ Returning all ${sortedData.length} measurements (sorted by latest first)`)
      return sortedData
    }
    
    const normalizedQuery = query.trim().toLowerCase()
    
    // Filter data based on query
    const filteredData = allData.filter(measurement => {
      const searchableText = [
        measurement.lot_id,
        measurement.recipe_name,
        measurement.date,
        measurement.formatted_date,
        measurement.slot_number?.toString(),
        measurement.measured_info?.toString()
      ].join(' ').toLowerCase()
      
      return searchableText.includes(normalizedQuery)
    })
    
    // Sort filtered results by date (latest first)
    const sortedData = filteredData.sort((a, b) => {
      const dateA = new Date(a.formatted_date)
      const dateB = new Date(b.formatted_date)
      return dateB - dateA
    })
    
    console.log(`✅ Filtered to ${sortedData.length} measurements matching "${query}"`)
    return sortedData
    
  } catch (error) {
    console.error('❌ Local filter error:', error)
    return []
  }
}


// Updated functions to use real pickle data
export async function fetchProfileData(filename, point, toolName = 'MAP608') {
  console.log(`📊 fetchProfileData called for filename: ${filename}, point: ${point}, tool: ${toolName}`)
  
  try {
    // Remove .csv extension from filename if present
    const cleanFilename = filename.replace('.csv', '')
    
    // Keep the full measurement point with site info (e.g., "1_UL")
    // The backend needs this to construct the correct file path
    const pointNumber = point
    
    console.log(`🔄 Calling getProfileData with cleanFilename: ${cleanFilename}, pointNumber: ${pointNumber}`)
    
    const response = await afmService.getProfileData(cleanFilename, pointNumber, toolName)
    
    if (response.success && response.data) {
      console.log(`✅ Loaded ${response.data.length} profile data points for ${cleanFilename}, point ${pointNumber}`)
      return response.data
    } else {
      console.warn('⚠️ Failed to load profile data:', response.error)
      return []
    }
  } catch (error) {
    console.error('❌ Error fetching profile data:', error)
    return []
  }
}

export async function fetchMeasurementData(filename, toolName = 'MAP608') {
  console.log(`🔍 fetchMeasurementData called for filename: ${filename}, tool: ${toolName}`)
  
  try {
    const response = await afmService.getAfmFileDetail(filename, toolName)
    
    console.log(`📦 Raw API response:`, response)
    console.log(`📦 Response success:`, response.success)
    console.log(`📦 Response data keys:`, response.data ? Object.keys(response.data) : 'No data')
    
    if (response.success && response.data) {
      console.log(`✅ Loaded measurement data for ${filename}`)
      
      // Log detailed structure
      const data = response.data
      console.log(`📊 Information data:`, data.information)
      console.log(`📊 Summary data type:`, typeof data.summary, 'length:', Array.isArray(data.summary) ? data.summary.length : 'not array')
      console.log(`📊 Summary data sample:`, Array.isArray(data.summary) ? data.summary.slice(0, 2) : data.summary)
      console.log(`📊 Data records type:`, typeof data.data, 'length:', Array.isArray(data.data) ? data.data.length : 'not array')
      console.log(`📊 Available points:`, data.available_points)
      console.log(`📊 Raw data_status:`, data.raw_data_status)
      
      // Transform Flask response format to frontend expected format
      const transformedData = {
        ...response.data,
        // Map Flask keys to frontend expected keys
        info: data.information,           // information -> info
        summaryData: data.summary,        // summary -> summaryData for StatisticalInfoByPoints
        profileData: data.data,           // data -> profileData for charts
        // Keep original keys for backward compatibility
        information: data.information,
        summary: data.summary,
        data: data.data
      }
      
      console.log(`🔄 Transformed data keys:`, Object.keys(transformedData))
      console.log(`🔄 Frontend-expected info:`, transformedData.info ? 'Available' : 'Missing')
      console.log(`🔄 Frontend-expected summaryData:`, transformedData.summaryData ? 'Available' : 'Missing')
      console.log(`🔄 Frontend-expected profileData:`, transformedData.profileData ? 'Available' : 'Missing')
      
      return {
        success: true,
        data: transformedData
      }
    } else {
      console.warn('⚠️ Failed to load measurement data:', response.error)
      return {
        success: false,
        error: response.error,
        data: null
      }
    }
  } catch (error) {
    console.error('❌ Error fetching measurement data:', error)
    return {
      success: false,
      error: error.message,
      data: null
    }
  }
}

export async function fetchSummaryData(filename, toolName = 'MAP608') {
  console.log(`📊 fetchSummaryData called for filename: ${filename}, tool: ${toolName}`)
  
  try {
    const measurementResponse = await fetchMeasurementData(filename, toolName)
    
    if (measurementResponse.success && measurementResponse.data.summaryData) {
      console.log(`📊 Summary data found:`, measurementResponse.data.summaryData)
      return {
        success: true,
        data: measurementResponse.data.summaryData
      }
    } else {
      return {
        success: false,
        data: []
      }
    }
  } catch (error) {
    console.error('❌ Error fetching summary data:', error)
    return {
      success: false,
      data: []
    }
  }
}

// Mock identifierData for compatibility
export const identifierData = []