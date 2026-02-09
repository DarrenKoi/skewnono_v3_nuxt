# CD-SEM Equipment Data Structure

Type: pd.DataFrame with 2D structure (Columns: description and examples)

## Column Definitions

### fac_id
- **Description:** Facility identifier where equipment is located
- **Examples:** M10, M11, M14, M15, M16, R3
- **Format:** Alphanumeric, suggesting regional/divisional organization

### eqp_id
- **Description:** Unique equipment identifier
- **Examples:** ECXDX123, PCD456, MCD789, HCDX234, ACD567, VCD890
- **Format:** Mix of alphanumeric formats (vendor-specific prefixes + 3-digit numbers)

### eqp_model_cd
- **Description:** Equipment model code
- **Examples:**
  - HITACHI: CG6300, CG6320, CG6340, CG6360, CG6380
  - AMAT: TP3000, TP3500, TP4000, TP4500, PROVISION_10, PROVISION_20, VERITYSEM_4, VERITYSEM_5
- **Format:** Model series with version numbers

### eqp_grp_id
- **Description:** Equipment grouping identifier
- **Examples:** G-ECD-01, G-MCD-02, G-KCD-03, G-MDS-01, G-PCD-02, G-ACD-03
- **Format:** Prefix + 2-digit number (01-03)
- **Prefixes:** G-ECD-, G-MCD-, G-KCD-, G-MDS-, G-PCD-, G-ACD-

### vendor_nm
- **Description:** Vendor/manufacturer name
- **Values:** HITACHI, AMAT
- **Format:** String (uppercase)

### eqp_ip
- **Description:** Private IP address assigned to equipment
- **Examples:** 177.10.5.123, 197.168.1.45
- **Format:** IPv4 address, primarily in 177.x.x.x or 197.x.x.x ranges

### fab_name
- **Description:** Fabrication unit name (specific location within facility)
- **Examples:** M16A, M14B, M10C, R4 (R3 has R4, R stands for research center)
- **Format:** fac_id + suffix letter (A, B, or C)

### updt_dt
- **Description:** Last updated timestamp
- **Format:** datetime (YYYY-MM-DD HH:MM:SS)
- **Type:** pd.datetime64

### available
- **Description:** Equipment operational status
- **Values:** "On", "Off"
- **Format:** String

### version
- **Description:** Equipment software/firmware version
- **Values:** 1, 2, 3
- **Format:** Integer

## Data Type Summary

| Type | Columns |
|------|---------|
| String | fac_id, eqp_id, eqp_model_cd, eqp_grp_id, vendor_nm, eqp_ip, fab_name, available |
| Datetime | updt_dt |
| Integer | version |
