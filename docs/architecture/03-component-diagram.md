# Component Diagram

## Purpose

This document shows the **internal module structure** of RetailPulse and how the Python source, Terraform, and policies are organized into modules. It complements the [HLD](01-hld.md) (which is service-oriented) by showing the **codebase** structure.

## Repository structure (code modules)

```mermaid
graph TB
    subgraph App[src/ - Python application]
        Common[common.py<br/>BaseAgent, JobContext, agent decorator]
        Agents[agents/<br/>sales.py, support.py, returns.py]
        Tools[tools/<br/>catalog.py, price_compare.py, order.py, refund.py, voice.py]
        Lambdas[lambdas/<br/>orchestrator_handler.py, sales_handler.py, etc.]
    end

    subgraph Config[config/ - YAML]
        Datasources[datasources/<br/>catalog.yaml, products.yaml]
        ToolsCfg[tools/<br/>catalog.yaml, price_compare.yaml]
        Prompts[prompts/<br/>sales.yaml, support.yaml, returns.yaml]
    end

    subgraph Infra[infra/terraform/ - IaC]
        Modules[modules/<br/>catalog-bucket, orders-table, kb-vectors, lambdas, step-function, apigateway, cloudfront, iam]
        Envs[envs/<br/>dev.tfvars, staging.tfvars, prod.tfvars]
    end

    subgraph UI[ui/ - Static KB UI]
        HTML[index.html, app.js, style.css]
    end

    subgraph Scripts[scripts/]
        Bootstrap[bootstrap.sh]
        Data[data-curator/<br/>generate.py]
    end

    subgraph Tests[tests/]
        Unit[unit/]
        Integration[integration/]
    end

    Agents --> Common
    Agents --> Tools
    Tools --> Common
    Tools --> Datasources
    Agents --> Prompts
    Lambdas --> Agents
    Lambdas --> Tools
    Modules --> Agents
    Modules --> Prompts
    HTML --> Agents
```

## Python module dependency graph

```mermaid
graph TB
    common[common.py]
    agents_sales[agents/sales.py]
    agents_support[agents/support.py]
    agents_returns[agents/returns.py]
    tools_catalog[tools/catalog.py]
    tools_price[tools/price_compare.py]
    tools_order[tools/order.py]
    tools_refund[tools/refund.py]
    tools_voice[tools/voice.py]
    lambdas_orch[lambdas/orchestrator_handler.py]
    lambdas_sales[lambdas/sales_handler.py]
    lambdas_supp[lambdas/support_handler.py]
    lambdas_ret[lambdas/returns_handler.py]

    agents_sales --> common
    agents_support --> common
    agents_returns --> common
    tools_catalog --> common
    tools_price --> common
    tools_order --> common
    tools_refund --> common
    tools_voice --> common
    lambdas_orch --> common
    lambdas_orch --> agents_sales
    lambdas_orch --> agents_support
    lambdas_orch --> agents_returns
    lambdas_sales --> agents_sales
    lambdas_supp --> agents_support
    lambdas_ret --> agents_returns
```

## Terraform module dependency graph

```mermaid
graph TB
    main[main.tf]
    catalog_b[modules/catalog-bucket]
    orders[modules/orders-dynamodb]
    kb[modules/kb-s3-vectors]
    lambdas[modules/lambdas]
    sf[modules/step-function]
    eb[modules/eventbridge]
    api[modules/apigateway]
    cf[modules/cloudfront]
    iam[modules/iam]
    oidc[modules/oidc]
    s3ui[modules/ui-bucket]

    main --> catalog_b
    main --> orders
    main --> kb
    main --> lambdas
    main --> sf
    main --> eb
    main --> api
    main --> cf
    main --> s3ui
    main --> iam
    main --> resource_group
    catalog_b --> iam
    orders --> iam
    kb --> iam
    lambdas --> iam
    sf --> lambdas
    eb --> sf
    api --> lambdas
    cf --> s3ui
    lambdas --> kb
    lambdas --> orders
    lambdas --> catalog_b
    iam --> oidc
```

## Data flow at the component level

```mermaid
sequenceDiagram
    participant C as Customer
    participant W as Web Client
    participant GW as API Gateway
    participant SF as Step Function
    participant T as Transcribe Lambda
    participant O as Orchestrator Lambda
    participant A as Agent Lambda
    participant Tools as Tool Lambdas
    participant S3 as S3 Catalog
    participant DD as DynamoDB
    participant Pol as Polly Lambda

    C->>W: "I want to return order #12345"
    W->>GW: POST /v1/conversations
    GW->>SF: StartExecution
    SF->>T: Transcribe
    T-->>SF: transcript
    SF->>O: Classify intent
    O->>O: Bedrock classify
    O-->>SF: intent=returns
    SF->>A: ReturnsAgent
    A->>Tools: lookup_order
    Tools->>DD: Query
    DD-->>Tools: order data
    Tools-->>A: order
    A->>Tools: check_policy
    Tools->>S3: Get policy doc
    S3-->>Tools: policy
    Tools-->>A: eligible
    A-->>SF: response text
    SF->>Pol: Synthesize
    Pol-->>SF: audio
    SF-->>GW: success
    GW-->>W: response
```

## Configuration files

| Config | Validated by | Used by |
|---|---|---|
| `config/datasources/*.yaml` | Pydantic | Tools, agents |
| `config/tools/*.yaml` | Pydantic | Tool definitions |
| `config/prompts/*.yaml` | Pydantic | Agent system prompts |
| `config/embedders/*.yaml` | Pydantic | Embedder selection |
| `policies/*.rego` | `opa test` | Runtime guardrails |
| `infra/terraform/envs/*.tfvars` | `terraform validate` | Environment-specific config |

## OPA policy structure

```mermaid
graph TB
    subgraph OPA[OPA bundle]
        PII[datacurator.pii<br/>pii-redaction.rego]
        Profanity[retailpulse.profanity<br/>profanity.rego]
        Authz[retailpulse.authz<br/>authorization.rego]
        RateLimit[retailpulse.ratelimit<br/>rate-limit.rego]
        CX[retailpulse.cx<br/>customer-experience.rego]
    end

    PII --> Agents
    Profanity --> Agents
    Authz --> Agents
    RateLimit --> Agents
    CX --> Agents
```

The OPA bundle is **embedded** in the Lambda deployment package.

## Where each component lives

```
retailpulse-cx-agent/
├── src/
│   ├── common.py                 # BaseAgent, JobContext, @agent decorator
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── sales.py
│   │   ├── support.py
│   │   └── returns.py
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── catalog.py
│   │   ├── price_compare.py       # browser-use in Fargate
│   │   ├── order.py
│   │   ├── refund.py
│   │   └── voice.py               # Transcribe + Polly
│   ├── lambdas/
│   │   ├── __init__.py
│   │   ├── orchestrator_handler.py
│   │   ├── sales_handler.py
│   │   ├── support_handler.py
│   │   └── returns_handler.py
│   └── lambdas_layer/             # Shared layer (CrewAI, Strands)
├── policies/                      # OPA Rego
│   ├── profanity.rego
│   ├── authorization.rego
│   ├── rate-limit.rego
│   └── customer-experience.rego
├── prompts/                       # Agent system prompts
│   ├── sales.yaml
│   ├── support.yaml
│   └── returns.yaml
├── config/                        # YAML configs
│   ├── datasources/
│   ├── tools/
│   ├── embedders/
│   └── prompts/
├── infra/terraform/               # IaC
│   ├── main.tf
│   ├── variables.tf
│   ├── providers.tf
│   ├── data.tf
│   ├── locals.tf
│   ├── modules/
│   │   ├── catalog-bucket/
│   │   ├── orders-dynamodb/
│   │   ├── kb-vectors/
│   │   ├── lambdas/
│   │   ├── step-function/
│   │   ├── eventbridge/
│   │   ├── apigateway/
│   │   ├── cloudfront/
│   │   ├── iam/
│   │   ├── oidc/
│   │   ├── ui-bucket/
│   │   └── resource-group/
│   └── envs/
│       ├── dev.tfvars
│       ├── staging.tfvars
│       └── prod.tfvars
├── ui/                            # KB UI
│   ├── index.html
│   ├── app.js
│   ├── style.css
│   └── README.md
├── scripts/                       # Operational
│   ├── bootstrap.sh               # One-time AWS setup
│   ├── destroy.sh
│   └── verify.sh
├── data-curator/                  # Synthetic data generator
│   └── generate.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
└── docs/
    ├── architecture/
    ├── adr/
    ├── runbooks/
    └── api/
```

## See also

- [HLD](01-hld.md) — service boundaries
- [LLD](02-lld.md) — data shapes, code structure
- [Data flow](04-data-flow.md) — sequence diagrams
