# Architecture Overview

RetailPulse is a serverless, event-driven, multi-agent customer experience suite for retail. Three cooperating agents (Sales, Support, Returns) share a knowledge base, take natural-language requests, and act on a real retail catalog and order history. Config-driven, cloud-portable, voice-enabled.

## System context

```mermaid
graph TB
    subgraph External[External systems]
        C[Customer]
        S1[Amazon]
        S2[Walmart]
        S3[Target]
        D[ShipStation / 3PL]
    end

    subgraph RP[RetailPulse]
        Channels[Voice / Web / API]
        Orchestrator[Step Function<br/>Orchestrator]
        Sales[Sales Agent]
        Support[Support Agent]
        Returns[Returns Agent]
        Tools[Tool Layer]
        Storage[Storage]
    end

    C --> Channels
    Channels --> Orchestrator
    Orchestrator --> Sales
    Orchestrator --> Support
    Orchestrator --> Returns
    Sales --> Tools
    Support --> Tools
    Returns --> Tools
    Tools --> Storage
    Sales --> S1
    Sales --> S2
    Sales --> S3
    Returns --> D
```

## High-level architecture

```mermaid
graph TB
    subgraph Channels
        VC[Voice Client<br/>LiveKit / Polly]
        WC[Web Client]
        AP[API / SDK]
    end
    subgraph Edge
        CF[CloudFront]
        GW[API Gateway<br/>HTTP API]
    end
    subgraph Orchestration
        SF[Step Function<br/>retailpulse-pipeline]
        ORC[Orchestrator Lambda]
    end
    subgraph Agents[CrewAI Agents]
        SA[Sales Agent]
        SU[Support Agent]
        RA[Returns Agent]
    end
    subgraph Tools
        CT[Catalog Tool]
        PT[Price Compare<br/>Fargate + browser-use]
        OT[Order Lookup]
        FT[FAQ RAG]
        RT[Refund Tool]
        TT[Transcribe + Polly]
    end
    subgraph Storage
        CAT[(Catalog<br/>S3 + DDB)]
        ORD[(Orders<br/>DDB)]
        KB[(KB Vectors<br/>S3 Vectors)]
        FB[(Feedback<br/>DDB)]
    end
    VC --> TT
    WC --> CF
    AP --> GW
    CF --> GW
    GW --> SF
    SF --> ORC
    ORC --> SA
    ORC --> SU
    ORC --> RA
    SA --> CT
    SA --> PT
    SU --> OT
    SU --> FT
    RA --> OT
    RA --> RT
    CT --> CAT
    OT --> ORD
    PT --> KB
    FT --> KB
    RT --> CAT
    SA & SU & RA --> FB
```

Full architecture: see [`01-hld.md`](01-hld.md).

## Key flows

### Voice conversation flow

1. Customer speaks → voice gateway → Amazon Transcribe (STT)
2. Text → API Gateway → Step Function → Orchestrator Lambda
3. Orchestrator dispatches to one of 3 agents (Sales/Support/Returns) based on intent
4. Agent calls tools (catalog lookup, price compare, order history, etc.)
5. Agent generates response text → Amazon Polly (TTS) → audio to customer

### Browser price comparison flow

1. Customer asks "is this a good price?"
2. Sales agent invokes `compare_price` tool
3. Tool starts an ECS Run Task with a browser-use container
4. Fargate task launches headless Chromium, navigates Amazon/Walmart/Target
5. Extracts structured price data
6. Returns comparison + recommendation to agent
7. Agent responds to customer

### Returns flow

1. Customer asks "I want to return my order"
2. Returns agent calls `lookup_order` to verify the order
3. Agent checks return policy (RAG over policy docs)
4. If eligible, agent calls `initiate_refund` which calls 3PL API
5. Agent sends confirmation (voice or text)
6. Feedback recorded in DynamoDB

## Why this design

| Concern | Decision | Why |
|---|---|---|
| Multi-agent | CrewAI | First-class multi-agent, role-based prompts, tool-calling |
| AWS integration | Strands Agents | AWS-native, lightweight, complements CrewAI |
| Browser tools | browser-use in Fargate | Real-time data, free, shows agentic capability |
| Storage | S3 Vectors | $0 idle, 1000× cheaper than OpenSearch Serverless |
| Auth | GitHub OIDC | No long-lived secrets, scoped to repo+branch |
| IaC | Terraform | Cloud-portable, mature tooling, recruiter-friendly |
| Voice | Polly + Transcribe | AWS-native, $4/1M chars, good EN-IN voices |
| Embeddings | Titan v2 | Cheapest in-region, multilingual |

## Where to read next

- [HLD](01-hld.md) — service boundaries, deployment topology
- [LLD](02-lld.md) — data shapes, code structure
- [Component diagram](03-component-diagram.md) — module dependencies
- [Data flow](04-data-flow.md) — sequence diagrams
- [Security model](06-security-model.md) — threat model, trust boundaries
- [Cost model](07-cost-model.md) — per-component cost
