# Define assessment storage, freshness, and API contracts

Parent: [Trustworthy MSR review detection](../map.md)
Type: grilling
Status: open
Blocked by: 02, 04
Blocked by tickets: [Inventory office MSR storage and retrieval constraints](02-inventory-office-msr-storage-and-retrieval-constraints.md), [Define review evidence and quality-gate semantics](04-define-review-evidence-and-quality-gate-semantics.md)

## Question

What versioned persistence and API contracts keep OpenSearch review summaries consistent with MinIO-backed evidence while preserving the existing frontend/backend swap boundary? Decide whether summaries are embedded or separately indexed, how assessment and detector versions are identified, how stale or missing assessments appear, what the normalized single and batch MSR responses contain, how partial batch failures are represented, and where precomputation and re-evaluation occur.
