# SEM List Data Structure

Type: backend response array for the SEM equipment inventory endpoint (`/mock-api/sem-list`)

Source of truth for all SEM equipment regardless of tool type (CD-SEM, HV-SEM, etc.).
Mirrors the shape of the legacy Python generator so Flask can drop in later without a schema change.

## Column Definitions

### fac_id
- **Description:** Facility identifier the equipment belongs to
- **Values:** `R3`, `M11`, `M12`, `M14`, `M15`, `M16`
- **Format:** Uppercase string

### eqp_id
- **Description:** Unique equipment identifier
- **Examples:** `ECDX123`, `HCDX456`, `PCD789`
- **Format:** Vendor-specific prefix + 3-digit numeric suffix

### eqp_model_cd
- **Description:** Equipment model code
- **Examples:** `CG6380`, `GT2000S`, `PROVISION_20`, `VERITYSEM_5`, `TP4000`
- **Format:** Vendor-specific model series code. Prefix determines tool-type classification (`CG*` / `GT*` → CD-SEM, `TP*` → HV-SEM, `VERITYSEM_*` → VeritySEM, `PROVISION_*` → Provision).

### eqp_grp_id
- **Description:** Equipment group identifier used for routing / recipe grouping
- **Examples:** `G-ECD-01`, `G-MCD-02`, `G-PCD-03`
- **Format:** `G-<measurement>-<2-digit index>`

### vendor_nm
- **Description:** Equipment vendor
- **Values:** `HITACHI`, `AMAT`
- **Format:** Uppercase string

### eqp_ip
- **Description:** Private IP address assigned to equipment
- **Examples:** `177.30.1.101`, `197.168.12.34`
- **Format:** IPv4 string (prefix `177.x.x.x` or `197.x.x.x`)

### fab_name
- **Description:** Fab identifier; usually `<fac_id><A|B|C>`, with occasional `R4` for R3 overflow
- **Examples:** `R3A`, `M11B`, `M14C`, `R4`
- **Format:** Uppercase string

### updt_dt
- **Description:** Last update timestamp (within the prior 90 days)
- **Format:** ISO 8601 UTC string (e.g. `2026-03-15T00:00:00.000Z`)

### available
- **Description:** Tool availability status
- **Values:** `On`, `Off` (≈90% On)
- **Format:** String

### version
- **Description:** Equipment model version
- **Values:** 1–3
- **Format:** Integer

## Data Type Summary

| Type | Columns |
|------|---------|
| String | fac_id, eqp_id, eqp_model_cd, eqp_grp_id, vendor_nm, eqp_ip, fab_name, updt_dt, available |
| Integer | version |

## Generation

Rows are produced by `generateSemList(nRows = 300, seed = 42)` using a seeded mulberry32 PRNG
so output is deterministic across reloads — mirroring `np.random.seed(42)` in the original
Python generator (`generate_equipment_data`).
