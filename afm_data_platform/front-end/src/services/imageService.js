import api from './api'

/**
 * Image Service
 * Handles image retrieval and serving from different directories
 */
export const imageService = {
  // Get profile image for a specific measurement point and tool (legacy)
  async getProfileImage(filename, pointNumber, toolName = 'MAP608', siteInfo = null) {
    console.log(`🔍 [API] Fetching profile image for filename: "${filename}", point: ${pointNumber} from tool: ${toolName}`)
    if (siteInfo) {
      console.log(`📍 [API] Site info provided:`, siteInfo)
    }
    
    const params = new URLSearchParams({ tool: toolName })
    if (siteInfo) {
      if (siteInfo.site_id !== null) params.append('site_id', siteInfo.site_id)
      if (siteInfo.site_x !== null) params.append('site_x', siteInfo.site_x)
      if (siteInfo.site_y !== null) params.append('site_y', siteInfo.site_y)
      if (siteInfo.point_no !== null) params.append('point_no', siteInfo.point_no)
    }
    
    console.log(`🔗 [API] Image request URL: /afm-files/image/${encodeURIComponent(filename)}/${encodeURIComponent(pointNumber)}?${params}`)
    const response = await api.get(`/afm-files/image/${encodeURIComponent(filename)}/${encodeURIComponent(pointNumber)}?${params}`)
    console.log('📊 [API] Profile image response:', response)
    return response
  },

  // Get the URL for serving a profile image (legacy)
  getProfileImageUrl(filename, pointNumber, toolName = 'MAP608', siteInfo = null) {
    const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api'
    const params = new URLSearchParams({ tool: toolName })
    
    if (siteInfo) {
      if (siteInfo.site_id !== null) params.append('site_id', siteInfo.site_id)
      if (siteInfo.site_x !== null) params.append('site_x', siteInfo.site_x)
      if (siteInfo.site_y !== null) params.append('site_y', siteInfo.site_y)
      if (siteInfo.point_no !== null) params.append('point_no', siteInfo.point_no)
    }
    
    const url = `${baseUrl}/afm-files/image-file/${encodeURIComponent(filename)}/${encodeURIComponent(pointNumber)}?${params}`
    console.log(`🔗 [API] Image URL generated: ${url}`)
    return url
  },

  // Get images by directory type (NEW: for AdditionalAnalysisImages component)
  async getImagesByType(imageType, filename = null, pointId = 'default', toolName = 'MAP608') {
    console.log(`🖼️ Fetching ${imageType} images for filename: "${filename}", tool: ${toolName}`)
    const params = new URLSearchParams({ tool: toolName, point_id: pointId })
    
    if (filename) {
      params.append('filename', filename)
    }
    
    const response = await api.get(`/afm-files/images/${imageType}?${params}`)
    console.log(`📊 ${imageType} images response:`, response)
    return response
  },

  // Get URL for serving image by type (NEW: for AdditionalAnalysisImages component)
  getImageUrlByType(filename, pointId, imageType, imageName, toolName = 'MAP608') {
    const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api'
    const params = new URLSearchParams({ tool: toolName })
    
    const url = `${baseUrl}/afm-files/image-file/${encodeURIComponent(filename)}/${encodeURIComponent(pointId)}/${imageType}/${encodeURIComponent(imageName)}?${params}`
    console.log(`🔗 [API] Typed image URL generated: ${url}`)
    return url
  }
}