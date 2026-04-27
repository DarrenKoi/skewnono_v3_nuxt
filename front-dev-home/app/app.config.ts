export default defineAppConfig({
  ui: {
    colors: {
      primary: 'zinc',
      neutral: 'zinc'
    },
    header: {
      slots: {
        root: 'h-(--ui-header-height) sticky top-0 z-50 border-b-(--sk-nav-border) bg-(--sk-nav-bg) backdrop-blur-md shadow-none'
      }
    }
  }
})
