# ADR-0002: Use CrewAI as the primary agent orchestration framework

- **Status**: Accepted
- **Date**: 2026-08-27
- **Deciders**: Vijay Madhu, Mavis
- **Tags**: agents, framework, orchestration

## Context and problem statement

RetailPulse needs three cooperating agents (Sales, Support, Returns) that share context, hand off tasks, and call tools. We need a Python-native agent framework that supports:

- **Multi-agent** with role-based prompts and shared memory
- **Tool-calling** for catalog lookup, price compare, order history, refund
- **Handoffs** between agents (e.g., Sales → Returns after a "cancel order" intent)
- **Async** for long-running operations (browser-based price compare)
- **Vendor-neutral** so we can swap Claude / Bedrock / OpenAI without rewriting agent code

## Decision drivers

- Multi-agent is the core requirement (three named agents)
- Tool-calling is non-negotiable
- Python-native (matches the rest of the AWS serverless stack)
- Active community + long-term maintainability
- Cost-aware: prefer token-efficient frameworks
- Cloud-portable (we may move to Azure / GCP later)

## Considered options

### Option 1: CrewAI (chosen)

- ✅ **First-class multi-agent** with `Agent`, `Task`, `Crew` abstractions
- ✅ Role-based prompts, shared memory, agent delegation
- ✅ Built-in tool framework (`crewai_tools` package)
- ✅ Async-first; works well with FastAPI / Lambda
- ✅ Supports any LiteLLM-compatible model (Bedrock, OpenAI, Anthropic, etc.)
- ⚠️ Younger than LangChain; some rough edges
- ⚠️ Heavier than bare LLM calls

### Option 2: LangGraph

- ✅ **Graph-based** — explicit control flow, great for complex branching
- ✅ LangSmith observability
- ✅ Strong for stateful long-running workflows
- ⚠️ Steeper learning curve
- ⚠️ Multi-agent requires more boilerplate

### Option 3: OpenAI Agents SDK

- ✅ Official OpenAI SDK, simple primitives
- ✅ Built-in tracing
- ❌ OpenAI-only at the model layer (can route via LiteLLM but not first-class)
- ❌ Smaller community for multi-agent patterns

### Option 4: AWS Bedrock AgentCore (Strands)

- ✅ AWS-native
- ✅ Tight Bedrock integration
- ❌ Vendor-locked
- ❌ Strands is relatively new

## Decision outcome

**Chosen option 1: CrewAI** for the agent orchestration layer, with **Strands Agents / Bedrock AgentCore** as a secondary framework (per ADR-0003) for AWS-native service integration points.

### Consequences

**Positive**

- Agent definitions are readable Python — recruiter-friendly
- Easy to swap models (Bedrock, Anthropic, OpenAI) via LiteLLM
- Tool framework is clean and extensible
- Active community with regular releases

**Negative**

- Smaller ecosystem than LangChain
- Some advanced patterns (e.g., dynamic graph routing) are less mature
- Need to write our own observability (CrewAI has built-in tracing but we want Datadog/CloudWatch)

### Confirmation

- All 3 agents (Sales, Support, Returns) successfully answer sample queries
- p95 tool-call latency < 2s for catalog lookup; < 10s for browser compare
- Feedback loop captures ratings; weekly DSPy optimization improves accuracy

## Pros and cons of the options

| Option | Multi-agent | Tool-calling | Vendor-neutral | Community | Maturity |
|---|---|---|---|---|---|
| **CrewAI** | ✅ Native | ✅ Built-in | ✅ LiteLLM | Active | Medium |
| LangGraph | ✅ Native | ✅ Good | ✅ Yes | Active | High |
| OpenAI Agents | ⚠️ Basic | ✅ Good | ❌ OpenAI-only | Growing | Medium |
| Bedrock AgentCore | ✅ Via Strands | ✅ Good | ❌ AWS-only | Smaller | Low |

## References

- [CrewAI docs](https://docs.crewai.com/)
- [LangGraph vs CrewAI comparison](https://www.langchain.com/langgraph)
- [LiteLLM providers](https://docs.litellm.ai/docs/providers)
