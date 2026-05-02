/**
 * Services Index
 * Central export point for all services and axios configuration
 */

import axios from "axios";

// Create axios instance with base configuration
const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api",
  timeout: 15000,
  headers: {
    "Content-Type": "application/json",
  },
});

// Response interceptor to auto-extract data (keeps existing service compatibility)
api.interceptors.response.use(
  (response) => response.data,
  (error) => Promise.reject(error)
);

// Export base API instance
export default api
export { api }

// Export specialized services
export { activityService } from './activityService'
export { afmService } from './afmService' 
export { imageService } from './imageService'

// Export data processing functions
export {
  filterMeasurementsLocally,
  fetchProfileData,
  fetchMeasurementData,
  fetchSummaryData,
  identifierData
} from './dataService'

// Combined API service object for backward compatibility
import { activityService } from './activityService'
import { afmService } from './afmService'
import { imageService } from './imageService'

export const apiService = {
  ...activityService,
  ...afmService,
  ...imageService
}