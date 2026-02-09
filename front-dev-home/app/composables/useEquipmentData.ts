export interface Equipment {
  fac_id: string
  eqp_id: string
  eqp_model_cd: string
  eqp_grp_id: string
  vendor_nm: 'HITACHI' | 'AMAT'
  eqp_ip: string
  fab_name: string
  updt_dt: string
  available: 'On' | 'Off'
  version: number
}

const mockEquipmentData: Equipment[] = [
  // M10 - HITACHI
  { fac_id: 'M10', eqp_id: 'ECXDX101', eqp_model_cd: 'CG6300', eqp_grp_id: 'G-ECD-01', vendor_nm: 'HITACHI', eqp_ip: '177.10.5.101', fab_name: 'M10A', updt_dt: '2025-12-01 08:30:00', available: 'On', version: 3 },
  { fac_id: 'M10', eqp_id: 'ECXDX102', eqp_model_cd: 'CG6320', eqp_grp_id: 'G-ECD-01', vendor_nm: 'HITACHI', eqp_ip: '177.10.5.102', fab_name: 'M10A', updt_dt: '2025-12-01 09:15:00', available: 'On', version: 2 },
  { fac_id: 'M10', eqp_id: 'MCD103', eqp_model_cd: 'CG6340', eqp_grp_id: 'G-MCD-02', vendor_nm: 'HITACHI', eqp_ip: '177.10.5.103', fab_name: 'M10B', updt_dt: '2025-11-30 14:20:00', available: 'Off', version: 2 },
  { fac_id: 'M10', eqp_id: 'ACD104', eqp_model_cd: 'TP3000', eqp_grp_id: 'G-ACD-03', vendor_nm: 'AMAT', eqp_ip: '177.10.5.104', fab_name: 'M10C', updt_dt: '2025-12-01 07:45:00', available: 'On', version: 1 },

  // M11 - Mixed vendors
  { fac_id: 'M11', eqp_id: 'HCDX201', eqp_model_cd: 'CG6360', eqp_grp_id: 'G-ECD-01', vendor_nm: 'HITACHI', eqp_ip: '177.11.2.201', fab_name: 'M11A', updt_dt: '2025-12-01 10:00:00', available: 'On', version: 3 },
  { fac_id: 'M11', eqp_id: 'HCDX202', eqp_model_cd: 'CG6380', eqp_grp_id: 'G-ECD-01', vendor_nm: 'HITACHI', eqp_ip: '177.11.2.202', fab_name: 'M11A', updt_dt: '2025-12-01 10:05:00', available: 'On', version: 3 },
  { fac_id: 'M11', eqp_id: 'PCD203', eqp_model_cd: 'TP3500', eqp_grp_id: 'G-PCD-02', vendor_nm: 'AMAT', eqp_ip: '177.11.2.203', fab_name: 'M11B', updt_dt: '2025-11-29 16:30:00', available: 'Off', version: 2 },
  { fac_id: 'M11', eqp_id: 'PCD204', eqp_model_cd: 'PROVISION_10', eqp_grp_id: 'G-PCD-02', vendor_nm: 'AMAT', eqp_ip: '177.11.2.204', fab_name: 'M11B', updt_dt: '2025-12-01 06:00:00', available: 'On', version: 1 },

  // M14 - AMAT heavy
  { fac_id: 'M14', eqp_id: 'ACD301', eqp_model_cd: 'TP4000', eqp_grp_id: 'G-ACD-03', vendor_nm: 'AMAT', eqp_ip: '197.168.1.45', fab_name: 'M14A', updt_dt: '2025-12-01 11:20:00', available: 'On', version: 2 },
  { fac_id: 'M14', eqp_id: 'ACD302', eqp_model_cd: 'TP4500', eqp_grp_id: 'G-ACD-03', vendor_nm: 'AMAT', eqp_ip: '197.168.1.46', fab_name: 'M14A', updt_dt: '2025-12-01 11:25:00', available: 'On', version: 2 },
  { fac_id: 'M14', eqp_id: 'VCD303', eqp_model_cd: 'VERITYSEM_4', eqp_grp_id: 'G-KCD-03', vendor_nm: 'AMAT', eqp_ip: '197.168.1.47', fab_name: 'M14B', updt_dt: '2025-11-28 22:10:00', available: 'Off', version: 1 },
  { fac_id: 'M14', eqp_id: 'MCD304', eqp_model_cd: 'CG6300', eqp_grp_id: 'G-MCD-02', vendor_nm: 'HITACHI', eqp_ip: '197.168.1.48', fab_name: 'M14B', updt_dt: '2025-12-01 08:00:00', available: 'On', version: 3 },

  // M15 - HITACHI heavy
  { fac_id: 'M15', eqp_id: 'ECXDX401', eqp_model_cd: 'CG6340', eqp_grp_id: 'G-ECD-01', vendor_nm: 'HITACHI', eqp_ip: '177.15.3.401', fab_name: 'M15A', updt_dt: '2025-12-01 12:00:00', available: 'On', version: 3 },
  { fac_id: 'M15', eqp_id: 'ECXDX402', eqp_model_cd: 'CG6360', eqp_grp_id: 'G-ECD-01', vendor_nm: 'HITACHI', eqp_ip: '177.15.3.402', fab_name: 'M15A', updt_dt: '2025-12-01 12:05:00', available: 'On', version: 2 },
  { fac_id: 'M15', eqp_id: 'MCD403', eqp_model_cd: 'CG6380', eqp_grp_id: 'G-MDS-01', vendor_nm: 'HITACHI', eqp_ip: '177.15.3.403', fab_name: 'M15B', updt_dt: '2025-11-30 18:45:00', available: 'Off', version: 2 },
  { fac_id: 'M15', eqp_id: 'PCD404', eqp_model_cd: 'PROVISION_20', eqp_grp_id: 'G-PCD-02', vendor_nm: 'AMAT', eqp_ip: '177.15.3.404', fab_name: 'M15C', updt_dt: '2025-12-01 07:30:00', available: 'On', version: 1 },

  // M16 - Mixed
  { fac_id: 'M16', eqp_id: 'HCDX501', eqp_model_cd: 'CG6320', eqp_grp_id: 'G-ECD-01', vendor_nm: 'HITACHI', eqp_ip: '177.16.8.501', fab_name: 'M16A', updt_dt: '2025-12-01 13:00:00', available: 'On', version: 3 },
  { fac_id: 'M16', eqp_id: 'ACD502', eqp_model_cd: 'TP3000', eqp_grp_id: 'G-ACD-03', vendor_nm: 'AMAT', eqp_ip: '177.16.8.502', fab_name: 'M16A', updt_dt: '2025-12-01 13:10:00', available: 'On', version: 2 },
  { fac_id: 'M16', eqp_id: 'VCD503', eqp_model_cd: 'VERITYSEM_5', eqp_grp_id: 'G-KCD-03', vendor_nm: 'AMAT', eqp_ip: '177.16.8.503', fab_name: 'M16B', updt_dt: '2025-11-29 20:00:00', available: 'Off', version: 1 },
  { fac_id: 'M16', eqp_id: 'MCD504', eqp_model_cd: 'CG6340', eqp_grp_id: 'G-MCD-02', vendor_nm: 'HITACHI', eqp_ip: '177.16.8.504', fab_name: 'M16B', updt_dt: '2025-12-01 09:45:00', available: 'On', version: 2 },

  // R3 - Research center
  { fac_id: 'R3', eqp_id: 'ECXDX601', eqp_model_cd: 'CG6380', eqp_grp_id: 'G-ECD-01', vendor_nm: 'HITACHI', eqp_ip: '177.30.1.601', fab_name: 'R4', updt_dt: '2025-12-01 14:00:00', available: 'On', version: 3 },
  { fac_id: 'R3', eqp_id: 'ACD602', eqp_model_cd: 'TP4000', eqp_grp_id: 'G-ACD-03', vendor_nm: 'AMAT', eqp_ip: '177.30.1.602', fab_name: 'R4', updt_dt: '2025-12-01 14:15:00', available: 'On', version: 2 },
  { fac_id: 'R3', eqp_id: 'VCD603', eqp_model_cd: 'VERITYSEM_4', eqp_grp_id: 'G-KCD-03', vendor_nm: 'AMAT', eqp_ip: '177.30.1.603', fab_name: 'R4', updt_dt: '2025-11-30 10:30:00', available: 'Off', version: 1 },
  { fac_id: 'R3', eqp_id: 'MCD604', eqp_model_cd: 'CG6300', eqp_grp_id: 'G-MDS-01', vendor_nm: 'HITACHI', eqp_ip: '177.30.1.604', fab_name: 'R4', updt_dt: '2025-12-01 06:30:00', available: 'On', version: 2 },
]

export const useEquipmentData = () => {
  const fetchEquipmentList = (): Promise<Equipment[]> => {
    return Promise.resolve(mockEquipmentData)
  }

  const fetchEquipmentByFacility = (facId: string): Promise<Equipment[]> => {
    const filtered = mockEquipmentData.filter(e => e.fac_id === facId)
    return Promise.resolve(filtered)
  }

  const fetchEquipmentByVendor = (vendor: Equipment['vendor_nm']): Promise<Equipment[]> => {
    const filtered = mockEquipmentData.filter(e => e.vendor_nm === vendor)
    return Promise.resolve(filtered)
  }

  const fetchEquipmentById = (eqpId: string): Promise<Equipment | undefined> => {
    const equipment = mockEquipmentData.find(e => e.eqp_id === eqpId)
    return Promise.resolve(equipment)
  }

  return {
    fetchEquipmentList,
    fetchEquipmentByFacility,
    fetchEquipmentByVendor,
    fetchEquipmentById
  }
}
