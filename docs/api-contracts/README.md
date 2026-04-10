# API Contracts

Each YAML file defines one resource's API endpoints. Both the Nuxt mock server routes (Phase 1) and the Flask backend (Phase 2/3) must implement these contracts identically.

## Purpose

These contracts are the bridge between home (frontend) and work (backend) development. When you see real data at work, document its schema here. At home, Claude reads these contracts to generate TypeScript types and mock server routes.

## File Naming

One file per resource: `{resource}.yaml`

## Structure

```yaml
resource: equipment                    # resource name
description: What this resource is     # human-readable description
base_path: /api/equipment              # URL prefix

types:                                 # data type definitions
  Equipment:                           # type name
    field_name:
      type: string                     # string, integer, float, boolean, array
      description: What this field is
      examples: ["value1", "value2"]
      enum: ["A", "B"]                 # optional: fixed set of values
      format: "YYYY-MM-DD HH:MM:SS"   # optional: format hint

endpoints:                             # API endpoint definitions
  - path: /api/equipment
    method: GET
    description: What this endpoint does
    query_params:                      # optional: URL query parameters
      param_name:
        type: string
        required: false
        description: What it filters
    response:
      status: 200
      body:
        data:
          type: array
          items: Equipment             # reference to type above
        total:
          type: integer
    example_request: "GET /api/equipment?fac_id=M10"
    example_response:                  # one concrete example
      data:
        - { field: "value" }
      total: 1
```

## How Flask Should Read These

1. Each endpoint's `path` + `method` maps to a Flask route
2. `query_params` map to `request.args`
3. `response.body` defines the exact JSON shape to return
4. `types` define the data model (map to Python dataclass or dict keys)

## How Nuxt Mock Routes Should Read These

1. Each endpoint maps to a file in `server/api/`
2. `query_params` are read via `getQuery(event)`
3. Response shape matches `shared/types/` TypeScript interfaces
4. Mock data in `server/mock-data/` follows the type definitions
