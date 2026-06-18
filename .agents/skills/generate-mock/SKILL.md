---
name: generate-mock
description: Generate a mock data composable for a new API endpoint, following Phase 1 patterns.
argument-hint: [endpoint-name]
allowed-tools: Read, Grep, Glob, Write, Edit
---

# Generate Mock Data Composable

You are generating a mock data composable for the SKEWNONO project (Phase 1 — offline mode with mock data).

## Steps

### 1. Learn existing patterns

Read these files to understand the current conventions:

- `front-dev-home/app/composables/useEquipmentData.ts` — reference composable with typed interfaces, mock data array, and promise-based fetch functions
- `front-dev-home/app/composables/useToolData.ts` — simpler composable returning static config data
- `front-dev-home/app/mock-data/` — browse existing data description files for domain context and naming conventions

### 2. Parse the data description from the user's message

The user provides the data schema together with the `/generate-mock` invocation. Parse the following from their message:

- **Column/field names** and their descriptions
- **Example values** for each field
- **Data types** (string, number, datetime, boolean, etc.)
- **Format rules** (naming patterns, value ranges, enums)
- **Relationships** to other data (e.g., fac_id links to facility)

### 3. Generate the composable

Create `front-dev-home/app/composables/use<EndpointName>Data.ts` with:

#### TypeScript interface

- Define an `export interface` for the data shape
- Use union types for known enum values (e.g., `'On' | 'Off'`)
- Use `string` for datetime fields (ISO format strings)
- Use `number` for integer/float fields

#### Mock data array

- Generate **20-30 rows** of realistic data
- Cover all example values mentioned by the user (all fac_ids, vendors, models, etc.)
- Add comments grouping data by a logical dimension (e.g., by facility)
- Keep data realistic for the semiconductor metrology domain
- Mix statuses/states to simulate real-world distribution (mostly "On", some "Off")
- Use realistic timestamps spread across recent dates
- Follow IP, ID, and naming format patterns exactly as described

#### Promise-based fetch functions

All data access functions must return `Promise<T>` using `Promise.resolve()` to simulate async API calls. This ensures the composable can be swapped for real fetch calls in Phase 2/3 without code changes.

Provide these standard functions:

- `fetch<Name>List()` — returns all records
- `fetch<Name>By<PrimaryFilter>(value)` — filter by the most common dimension
- `fetch<Name>By<SecondaryFilter>(value)` — filter by another useful dimension
- `fetch<Name>ById(id)` — find a single record by unique ID

#### Composable export

```typescript
export const use<EndpointName>Data = () => {
  // ... functions ...
  return {
    fetchList,
    fetchByFilter,
    fetchById
  }
}
```

### 4. Save the data description

Also save the user's data description to `front-dev-home/app/mock-data/<endpoint-name>.md` as a reference file, formatted with:

- A title header
- Column definitions with description, examples, and format
- A data type summary table

### 5. Summary

After generating, report:

- The composable file path and interface name
- Number of mock records generated
- The fetch functions available
- The data description file path
