import { useQuery } from "@tanstack/vue-query";
import { computed } from "vue";
import { fetchMeasurementData, apiService } from "@/services/api";

/**
 * Vue Query composables for ResultPage data fetching
 */

// Query to fetch detailed measurement data for a specific file
export function useMeasurementData(filename, toolName = "MAP608") {
  return useQuery({
    queryKey: ["measurement-data", filename, toolName],
    queryFn: () => fetchMeasurementData(filename, toolName),
    enabled: !!filename,
    retry: 2,
  });
}

// Query to fetch profile data for a specific point
export function useProfileData(
  filename,
  pointNumber,
  toolName = "MAP608",
  siteInfo = null
) {
  return useQuery({
    queryKey: ["profile-data", filename, pointNumber, toolName, siteInfo],
    queryFn: () => {
      // Clean filename by removing .csv extension if present
      const cleanFilename = filename.replace(".csv", "");
      return apiService.getProfileData(
        cleanFilename,
        pointNumber,
        toolName,
        siteInfo
      );
    },
    enabled: !!(filename && pointNumber),
    retry: 1,
  });
}

// Query to fetch profile image for a specific point
export function useProfileImage(
  filename,
  pointNumber,
  toolName = "MAP608",
  siteInfo = null
) {
  return useQuery({
    queryKey: ["profile-image", filename, pointNumber, toolName, siteInfo],
    queryFn: async () => {
      // Clean filename by removing .csv extension if present
      const cleanFilename = filename.replace(".csv", "");
      const response = await apiService.getProfileImage(
        cleanFilename,
        pointNumber,
        toolName,
        siteInfo
      );

      if (response.success) {
        return {
          success: true,
          imageUrl: apiService.getProfileImageUrl(
            cleanFilename,
            pointNumber,
            toolName,
            siteInfo
          ),
        };
      }
      return response;
    },
    enabled: !!(filename && pointNumber),
    retry: 1,
  });
}

// Query to fetch wafer data for heatmap
export function useWaferData(filename, toolName = "MAP608") {
  return useQuery({
    queryKey: ["wafer-data", filename, toolName],
    queryFn: () => apiService.getWaferData(filename, toolName),
    enabled: !!filename,
    retry: 2,
  });
}

// Combined composable for ResultPage that provides all necessary data
export function useResultPageData(
  filename,
  selectedPoint,
  toolName = "MAP608"
) {
  // Main measurement data
  const measurementQuery = useMeasurementData(filename, toolName);

  // Profile data for selected point
  const profileQuery = useProfileData(
    filename,
    selectedPoint?.value,
    toolName,
    selectedPoint?.siteInfo
  );

  // Profile image for selected point
  const imageQuery = useProfileImage(
    filename,
    selectedPoint?.value,
    toolName,
    selectedPoint?.siteInfo
  );

  // Wafer data for heatmap
  const waferQuery = useWaferData(filename, toolName);

  // Computed properties for easier access to data
  const measurementInfo = computed(() => {
    if (!measurementQuery.data?.value?.success) {
      return {};
    }
    return measurementQuery.data.value.data?.info || {};
  });

  const summaryData = computed(() => {
    if (!measurementQuery.data?.value?.success) {
      return [];
    }

    const responseData = measurementQuery.data.value.data;
    // Try both summaryData and summary fields
    const summary = responseData?.summaryData || responseData?.summary || [];
    return Array.isArray(summary) ? summary : [];
  });

  const detailedData = computed(() => {
    if (!measurementQuery.data?.value?.success) {
      return [];
    }
    const detailed = measurementQuery.data.value.data?.profileData || [];
    return Array.isArray(detailed) ? detailed : [];
  });

  const measurementPoints = computed(() => {
    if (!measurementQuery.data?.value?.success) {
      return [];
    }
    const availablePoints =
      measurementQuery.data.value.data?.available_points || [];
    return availablePoints.map((point) => ({
      point: point,
      filename: filename,
    }));
  });

  const profileData = computed(() => {
    if (!profileQuery.data?.value?.success) {
      return [];
    }
    const profile = profileQuery.data.value.data || [];
    return Array.isArray(profile) ? profile : [];
  });

  const profileImageUrl = computed(() => {
    if (!imageQuery.data?.value?.success) {
      return null;
    }
    return imageQuery.data.value.imageUrl || null;
  });

  const waferData = computed(() => {
    if (!waferQuery.data?.value?.success) {
      return [];
    }
    const wafer = waferQuery.data.value.data || [];
    return Array.isArray(wafer) ? wafer : [];
  });

  // Loading states
  const isLoadingMeasurement = computed(() => measurementQuery.isLoading.value);
  const isLoadingProfile = computed(() => profileQuery.isLoading.value);
  const isLoadingProfileImage = computed(() => imageQuery.isLoading.value);
  const isLoadingWafer = computed(() => waferQuery.isLoading.value);

  // Error states
  const measurementError = computed(() => measurementQuery.error.value);
  const profileError = computed(() => profileQuery.error.value);
  const imageError = computed(() => imageQuery.error.value);
  const waferError = computed(() => waferQuery.error.value);

  // Check if we have any data
  const hasData = computed(() => {
    return (
      (measurementInfo.value &&
        Object.keys(measurementInfo.value).length > 0) ||
      (summaryData.value && summaryData.value.length > 0) ||
      (detailedData.value && detailedData.value.length > 0)
    );
  });

  return {
    // Queries
    measurementQuery,
    profileQuery,
    imageQuery,
    waferQuery,

    // Data
    measurementInfo,
    summaryData,
    detailedData,
    measurementPoints,
    profileData,
    profileImageUrl,
    waferData,

    // Loading states
    isLoadingMeasurement,
    isLoadingProfile,
    isLoadingProfileImage,
    isLoadingWafer,

    // Error states
    measurementError,
    profileError,
    imageError,
    waferError,

    // Computed
    hasData,
  };
}
