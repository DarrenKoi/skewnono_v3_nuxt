/**
 * Image Download Utilities
 * Provides functions for downloading individual images
 */

/**
 * Fetch an image as a blob from a URL
 * @param {string} url - The image URL
 * @returns {Promise<{blob: Blob, filename: string}>} - Blob data and extracted filename
 */
async function fetchImageAsBlob(url) {
  try {
    const response = await fetch(url)
    if (!response.ok) {
      throw new Error(`Failed to fetch image: ${response.statusText}`)
    }
    
    const blob = await response.blob()
    
    // Extract filename from URL or create a default one
    const urlPath = new URL(url).pathname
    const filename = urlPath.split('/').pop() || `image_${Date.now()}.png`
    
    return { blob, filename }
  } catch (error) {
    console.error('Error fetching image:', error)
    throw error
  }
}

/**
 * Download a single image
 * @param {string} url - The image URL
 * @param {string} filename - Optional filename (will extract from URL if not provided)
 */
export async function downloadSingleImage(url, filename = null) {
  try {
    const { blob, filename: extractedFilename } = await fetchImageAsBlob(url)
    const finalFilename = filename || extractedFilename
    const sanitizedName = sanitizeFilename(finalFilename)
    
    // Create download link and trigger download
    const downloadUrl = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = downloadUrl
    link.download = sanitizedName
    document.body.appendChild(link)
    link.click()
    
    // Clean up
    document.body.removeChild(link)
    window.URL.revokeObjectURL(downloadUrl)
    
    return { success: true, filename: sanitizedName }
  } catch (error) {
    console.error('Error downloading image:', error)
    throw error
  }
}

/**
 * Sanitize filename to remove invalid characters
 * @param {string} filename - Original filename
 * @returns {string} - Sanitized filename
 */
function sanitizeFilename(filename) {
  // Remove or replace invalid characters for file names
  return filename
    .replace(/[<>:"/\\|?*]/g, '_') // Replace invalid characters with underscore
    .replace(/\s+/g, '_') // Replace spaces with underscore
    .replace(/_{2,}/g, '_') // Replace multiple underscores with single
    .replace(/^_|_$/g, '') // Remove leading/trailing underscores
    || 'unnamed_file' // Fallback if filename becomes empty
}