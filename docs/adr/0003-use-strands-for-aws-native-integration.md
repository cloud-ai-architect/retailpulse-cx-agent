# ADR-0003: Use Strands Agents for AWS-native service integration

- **Status**: Accepted
- **Date**: 2026-08-27
- **Deciders**: Vijay Madhu, Mavis
- **Tags**: agents, aws, integration

## Context and problem statement

While CrewAI handles the primary multi-agent orchestration, certain integration points benefit from a framework with deep AWS service integration:

- Direct S3 read for catalog fetch
- DynamoDB query for order history with typed models
- EventBridge publish for "order cancelled" → downstream fulfillment
- Bedrock Converse API with structured output

We need a secondary framework that's AWS-native but still uses standard Python agent patterns.

## Decision drivers

- Deep AWS SDK integration (boto3 wrappers, IAM-aware)
- Lower boilerplate than raw boto3 for common patterns
- Doesn't replace CrewAI; complements it for specific tool implementations
- Avoids vendor lock-in at the *agent* level (we can swap CrewAI for LangGraph without rewriting AWS integrations)

## Considered options

### Option 1: Strands Agents (chosen)

- ✅ AWS-native, first-party SDK
- ✅ Built-in tools for S3, DynamoDB, EventBridge, Bedrock
- ✅ Maintained by AWS, follows AWS best practices
- ✅ Lightweight — can be used as a tool inside CrewAI
- ⚠️ Smaller community than LangChain

### Option 2: LangChain AWS integrations

- ✅ Mature, well-documented
- ⚠️ Heavy dependency tree
- ⚠️ Some abstractions leak AWS-specific concepts

### Option 3: Raw boto3

- ✅ Maximum control
- ❌ Verbose for common patterns
- ❌ No automatic retry / error handling

## Decision outcome

**Chosen option 1: Strands Agents** for AWS-specific tool implementations, used as a **tool provider inside CrewAI agents** (not as a competing orchestrator).

Pattern:

- Sales/Support/Returns agents are CrewAI `Agent` instances
- Their `tools` list includes Strands-wrapped AWS tools (`S3GetObjectTool`, `DynamoDBQueryTool`, `BedrockConverseTool`)
- CrewAI orchestrator decides which agent runs; the agent calls its tools; Strands handles the AWS API call

### Consequences

**Positive**

- AWS-first: best practices built in (retries, pagination, error handling)
- Lightweight; doesn't conflict with CrewAI
- Maintained by AWS team
- Easy to write typed tools with Pydantic

**Negative**

- Smaller community; fewer examples
- Some advanced patterns (multi-agent within Strands) — but we don't need them

### Confirmation

- All AWS-touching tools (S3, DynamoDB, EventBridge) wrapped in Strands
- No raw boto3 calls in business logic
- All tools have unit tests with moto mocks

## Pros and cons of the options

| Option | AWS-native | Boilerplate | Maintenance | Fits CrewAI |
|---|---|---|---|---|
| **Strands** | ✅ First-party | ✅ Low | ✅ AWS team | ✅ Clean |
| LangChain AWS | ⚠️ Wraps SDK | ⚠️ Medium | ✅ Community | ⚠️ Some friction |
| Raw boto3 | ✅ Native | ❌ High | ✅ AWS | ❌ Lots of code |

## References

- [Strands Agents docs](https://strandsagents.com/)
- [CrewAI custom tools](https://docs.crewai.com/core-concepts/Tools)
- [Strands Tools](https://github.com/strands-agents/tools)
