# Recent

```

# Recent

## 2026-07-22
Office provider adapters completed: recipe_search + fail_issue + lateral_recipe on Redis v3 and OpenSearch. Hardware providers split into 7 per-tab directories (FDC, sharpness, BSM, MDC, reso_center, mdc, sce) with office/mock fallback pattern; fixed critical bugs (redis hang, timezone normalization UTC→KST, MinIO paths, msr_file retrieval). UI improvements: recipe-search tokenized matching, cascade filters (+9 tests), scrollable chip strip; presence-detection wired; 188 BE + 485 FE tests.

## 2026-07-21
Office provider layer wiring complete: sem_list→office Redis (v3_df_sem_list+version merge, parquet), storage adapter (ppid+unavail hash), recipe_tat OpenSearch (meas_hist 15-field schema). Code quality: dedup −121L, fabId→fabName TS types, TimeoutError + pagination handlers. Docs: 4 new chapters + Korean humanization, progress_report generated (50pg/175comp/598test/636commit grade A); 143 backend tests pass; 2 agent reviews → 5 quick-fixes.

## 2026-07-20
Setup openwiki daily cron (01:00, wrapper+launchd). Consolidated 8 localStorage composables → usePersistedState factory; rejected Pinia. Redis adapter office.py (v3_sem_list fetch, env-based config, serialization tested). Fixed parquet deserializer, load_dotenv path, merged v3_df_sem_version→v3_df_sem_list (5 commits); live office UI verified.

## Identity Candidates
- IDENTITY CANDIDATE: Spec-driven sub-project sequencing with TDD + comprehensive testing (AFM A–D roadmap, Chat feature paired with dashboard polish)