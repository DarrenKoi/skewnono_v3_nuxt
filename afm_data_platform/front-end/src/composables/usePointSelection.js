import { ref } from "vue";

/**
 * Composable for handling point selection in ResultPage
 */
export function usePointSelection() {
  const selectedPoint = ref(null);

  // Simple point selection function
  function selectPoint(pointNumber) {
    console.log(`📍 Selecting point: ${pointNumber}`);
    selectedPoint.value = pointNumber;
  }

  // Handle point selection from MeasurementPoints component
  function handlePointSelected(pointData) {
    const {
      measurementPoint,
      pointNumber,
      filename: pointFilename,
      siteInfo,
    } = pointData;

    if (pointNumber && pointFilename) {
      console.log(`📍 Point selected:`, pointData);

      // Update selected point with site info for API calls
      selectedPoint.value = {
        value: pointNumber,
        measurementPoint,
        siteInfo,
        filename: pointFilename,
      };

      // Skip prefetching - let queries fetch on demand
      // This reduces unnecessary API calls
    }
  }

  // Handle wafer point selection from heatmap
  function handleWaferPointSelected(point) {
    console.log(`📍 Wafer point selected:`, point);

    if (point && point.point) {
      selectPoint(point.point);
    }
    // Removed undefined measurementPoints reference
  }

  // Handle point data loaded event (for compatibility)
  function handlePointDataLoaded(data) {
    console.log(`📊 Point data loaded:`, data);
    // Could be used to update UI state or trigger other actions
  }

  return {
    selectedPoint,
    selectPoint,
    handlePointSelected,
    handleWaferPointSelected,
    handlePointDataLoaded,
  };
}
