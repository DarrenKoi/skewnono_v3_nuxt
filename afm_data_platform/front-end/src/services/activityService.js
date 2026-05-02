import api from './api'

/**
 * User Activity Service
 * Handles user activity tracking and retrieval
 */
export const activityService = {
  // Health check
  async healthCheck() {
    return await api.get('/health')
  },

  // Get user activities
  async getUserActivities(userId = null, limit = 100) {
    console.log(`👤 Fetching user activities (user: ${userId}, limit: ${limit})`)
    const params = new URLSearchParams({ limit: limit.toString() })
    
    if (userId) {
      params.append('user', userId)
    }
    
    const response = await api.get(`/user-activities?${params}`)
    console.log('📊 User activities response:', response)
    return response
  },

  // Get current user's activities
  async getMyActivities() {
    console.log('👤 Fetching current user activities')
    const response = await api.get('/my-activities')
    console.log('📊 My activities response:', response)
    return response
  },

  // Get current user info
  async getCurrentUser() {
    console.log('👤 Fetching current user info')
    const response = await api.get('/current-user')
    console.log('📊 Current user response:', response)
    return response
  },

  // Debug cookies (development only)
  async debugCookies() {
    console.log('🔍 Debug: Fetching cookies info')
    const response = await api.get('/debug/cookies')
    console.log('📊 Debug cookies response:', response)
    return response
  }
}