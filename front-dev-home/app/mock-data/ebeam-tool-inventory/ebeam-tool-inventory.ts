import type { ToolType, Fab } from '~/stores/navigation'

export interface EbeamToolRow {
  fab_name: Exclude<Fab, 'all'>
  eqp_id: string
  eqp_model_cd: string
  eqp_ip: string
  version: number
  available: 'On' | 'Off'
}

export type EbeamToolInventoryResponse = Record<ToolType, EbeamToolRow[]>

export const mockEbeamToolInventoryResponse: EbeamToolInventoryResponse = {
  'cd-sem': [
    { fab_name: 'R3', eqp_id: 'CDR3001', eqp_model_cd: 'CG6380', eqp_ip: '177.30.1.101', version: 3, available: 'On' },
    { fab_name: 'R3', eqp_id: 'CDR3002', eqp_model_cd: 'CG6360', eqp_ip: '177.30.1.102', version: 2, available: 'Off' },
    { fab_name: 'M11', eqp_id: 'CDM1101', eqp_model_cd: 'CG6300', eqp_ip: '177.11.2.101', version: 3, available: 'On' },
    { fab_name: 'M11', eqp_id: 'CDM1102', eqp_model_cd: 'CG6320', eqp_ip: '177.11.2.102', version: 2, available: 'On' },
    { fab_name: 'M12', eqp_id: 'CDM1201', eqp_model_cd: 'CG6340', eqp_ip: '177.12.4.101', version: 2, available: 'On' },
    { fab_name: 'M12', eqp_id: 'CDM1202', eqp_model_cd: 'CG6360', eqp_ip: '177.12.4.102', version: 1, available: 'Off' },
    { fab_name: 'M14', eqp_id: 'CDM1401', eqp_model_cd: 'CG6380', eqp_ip: '197.168.1.101', version: 3, available: 'On' },
    { fab_name: 'M14', eqp_id: 'CDM1402', eqp_model_cd: 'CG6340', eqp_ip: '197.168.1.102', version: 2, available: 'On' },
    { fab_name: 'M15', eqp_id: 'CDM1501', eqp_model_cd: 'CG6300', eqp_ip: '177.15.3.101', version: 3, available: 'On' },
    { fab_name: 'M15', eqp_id: 'CDM1502', eqp_model_cd: 'CG6320', eqp_ip: '177.15.3.102', version: 2, available: 'Off' },
    { fab_name: 'M16', eqp_id: 'CDM1601', eqp_model_cd: 'CG6360', eqp_ip: '177.16.8.101', version: 3, available: 'On' },
    { fab_name: 'M16', eqp_id: 'CDM1602', eqp_model_cd: 'CG6380', eqp_ip: '177.16.8.102', version: 2, available: 'On' }
  ],
  'hv-sem': [
    { fab_name: 'R3', eqp_id: 'HVR3001', eqp_model_cd: 'HVS-7000', eqp_ip: '177.30.1.201', version: 4, available: 'On' },
    { fab_name: 'R3', eqp_id: 'HVR3002', eqp_model_cd: 'HVS-7100', eqp_ip: '177.30.1.202', version: 3, available: 'On' },
    { fab_name: 'M11', eqp_id: 'HVM1101', eqp_model_cd: 'HVS-7200', eqp_ip: '177.11.2.201', version: 4, available: 'On' },
    { fab_name: 'M11', eqp_id: 'HVM1102', eqp_model_cd: 'HVS-7000', eqp_ip: '177.11.2.202', version: 2, available: 'Off' },
    { fab_name: 'M12', eqp_id: 'HVM1201', eqp_model_cd: 'HVS-7100', eqp_ip: '177.12.4.201', version: 3, available: 'On' },
    { fab_name: 'M12', eqp_id: 'HVM1202', eqp_model_cd: 'HVS-7200', eqp_ip: '177.12.4.202', version: 3, available: 'On' },
    { fab_name: 'M14', eqp_id: 'HVM1401', eqp_model_cd: 'HVS-7000', eqp_ip: '197.168.1.201', version: 4, available: 'On' },
    { fab_name: 'M14', eqp_id: 'HVM1402', eqp_model_cd: 'HVS-7300', eqp_ip: '197.168.1.202', version: 2, available: 'Off' },
    { fab_name: 'M15', eqp_id: 'HVM1501', eqp_model_cd: 'HVS-7200', eqp_ip: '177.15.3.201', version: 4, available: 'On' },
    { fab_name: 'M15', eqp_id: 'HVM1502', eqp_model_cd: 'HVS-7300', eqp_ip: '177.15.3.202', version: 3, available: 'On' },
    { fab_name: 'M16', eqp_id: 'HVM1601', eqp_model_cd: 'HVS-7100', eqp_ip: '177.16.8.201', version: 3, available: 'On' },
    { fab_name: 'M16', eqp_id: 'HVM1602', eqp_model_cd: 'HVS-7300', eqp_ip: '177.16.8.202', version: 2, available: 'Off' }
  ],
  'verity-sem': [
    { fab_name: 'R3', eqp_id: 'VSR3001', eqp_model_cd: 'VERITYSEM_4', eqp_ip: '177.30.1.301', version: 1, available: 'On' },
    { fab_name: 'M11', eqp_id: 'VSM1101', eqp_model_cd: 'VERITYSEM_4', eqp_ip: '177.11.2.301', version: 1, available: 'On' },
    { fab_name: 'M12', eqp_id: 'VSM1201', eqp_model_cd: 'VERITYSEM_5', eqp_ip: '177.12.4.301', version: 2, available: 'Off' },
    { fab_name: 'M14', eqp_id: 'VSM1401', eqp_model_cd: 'VERITYSEM_5', eqp_ip: '197.168.1.301', version: 2, available: 'On' },
    { fab_name: 'M15', eqp_id: 'VSM1501', eqp_model_cd: 'VERITYSEM_4', eqp_ip: '177.15.3.301', version: 1, available: 'On' },
    { fab_name: 'M16', eqp_id: 'VSM1601', eqp_model_cd: 'VERITYSEM_5', eqp_ip: '177.16.8.301', version: 2, available: 'On' }
  ],
  'provision': [
    { fab_name: 'R3', eqp_id: 'PVR3001', eqp_model_cd: 'PROVISION_10', eqp_ip: '177.30.1.401', version: 1, available: 'On' },
    { fab_name: 'M11', eqp_id: 'PVM1101', eqp_model_cd: 'PROVISION_20', eqp_ip: '177.11.2.401', version: 2, available: 'On' },
    { fab_name: 'M12', eqp_id: 'PVM1201', eqp_model_cd: 'PROVISION_10', eqp_ip: '177.12.4.401', version: 1, available: 'Off' },
    { fab_name: 'M14', eqp_id: 'PVM1401', eqp_model_cd: 'PROVISION_20', eqp_ip: '197.168.1.401', version: 2, available: 'On' },
    { fab_name: 'M15', eqp_id: 'PVM1501', eqp_model_cd: 'PROVISION_20', eqp_ip: '177.15.3.401', version: 2, available: 'On' },
    { fab_name: 'M16', eqp_id: 'PVM1601', eqp_model_cd: 'PROVISION_10', eqp_ip: '177.16.8.401', version: 1, available: 'On' }
  ]
}
