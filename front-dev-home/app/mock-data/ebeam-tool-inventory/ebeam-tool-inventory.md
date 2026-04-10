# E-Beam Tool Inventory Data Structure

Type: backend response table for the e-beam tool list endpoint

Applies to: `cd-sem`, `hv-sem`, `verity-sem`, `provision`

## Column Definitions

### fab_name
- **Description:** Fab identifier used in the UI filter and sidebar
- **Examples:** R3, M11, M12, M14, M15, M16
- **Format:** Uppercase string

### eqp_id
- **Description:** Unique equipment identifier and tool id
- **Examples:** CDR3001, HVR3001, VSR3001, PVR3001
- **Format:** Tool prefix + fab code + numeric suffix

### eqp_model_cd
- **Description:** Equipment model name
- **Examples:** CG6380, HVS-7300, VERITYSEM_5, PROVISION_20
- **Format:** Model series code

### eqp_ip
- **Description:** Private IP address assigned to equipment
- **Examples:** 177.30.1.101, 177.30.1.201, 177.30.1.301, 177.30.1.401
- **Format:** IPv4 address

### version
- **Description:** Equipment model version
- **Values:** Integer version number by tool model
- **Format:** Integer

### available
- **Description:** Tool availability status
- **Values:** "On", "Off"
- **Format:** String

## Data Type Summary

| Type | Columns |
|------|---------|
| String | fab_name, eqp_id, eqp_model_cd, eqp_ip, available |
| Integer | version |
