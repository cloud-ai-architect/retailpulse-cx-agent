# ADR-0004: Use browser-use for browser-based price comparison

- **Status**: Accepted
- **Date**: 2026-08-27
- **Deciders**: Vijay Madhu, Mavis
- **Tags**: tools, scraping, browser

## Context and problem statement

The Sales agent needs to answer "is this product competitively priced?" by comparing against Amazon, Walmart, Target, etc. There are three options:

1. **Use a price comparison API** (e.g., Keepa, Rainforest API) — fast, but expensive per call and limited coverage
2. **Maintain a static price database** — stale, requires ETL
3. **Browse the competitor's site in real time** — freshest data, free, but complex

For a portfolio-quality demo that shows "real" agent behavior, option 3 is the most impressive and most accurate. It also handles edge cases (product not in our DB, new competitor, price changes) that options 1 and 2 miss.

## Decision drivers

- Real-time price data (no stale ETL)
- No per-call API cost
- Demonstrates agentic tool-use to recruiters
- Runs serverlessly (must work in Lambda or Fargate)
- Safe (no fraud / bot detection issues for portfolio)

## Considered options

### Option 1: `browser-use` library (chosen)

- ✅ Python-native, async
- ✅ Wraps Playwright; handles headless browser
- ✅ Designed for LLM-driven browsing (extract structured data from rendered pages)
- ✅ Active community, MIT-licensed
- ⚠️ ~100MB container (Playwright + Chromium)
- ⚠️ Some sites block headless browsers

### Option 2: Plain Playwright

- ✅ More flexible, lower-level
- ❌ More code to write (parsing logic, structured extraction)
- ❌ Reinventing what `browser-use` already provides

### Option 3: SerpAPI / similar

- ✅ Simple
- ❌ Per-call cost
- ❌ Less impressive as a demo

## Decision outcome

**Chosen option 1: `browser-use` library**, deployed as a separate AWS Fargate task (not Lambda, because the Chromium binary exceeds Lambda's 250MB deployment limit).

Pattern:
- CrewAI Sales agent exposes a `compare_price(product_name: str) -> PriceComparison` tool
- Tool implementation: invoke browser-use in a Fargate task via ECS Run Task API
- Fargate pulls product name, navigates Amazon/Walmart/Target, extracts prices
- Returns structured `PriceComparison` (cheapest, average, our price, recommendation)

### Consequences

**Positive**

- Real, fresh data — no stale ETL
- Shows off agentic tool use
- ~$0.10/hour for Fargate Spot = effectively free at demo volumes

**Negative**

- Cold start ~30s (Fargate task spin-up)
- Some sites block headless Chrome
- Need to handle timeouts and partial results

### Confirmation

- `compare_price` returns within 30s for 80% of queries
- Price extraction accuracy > 90% on Amazon/Walmart/Target
- Cost < $1/month at demo usage

## Pros and cons of the options

| Option | Freshness | Cost | Demo-ability | Reliability |
|---|---|---|---|---|
| **browser-use** | ✅ Real-time | ✅ Free | ✅ High | ⚠️ 90% |
| Plain Playwright | ✅ Real-time | ✅ Free | ⚠️ Medium | ⚠️ 90% |
| SerpAPI | ⚠️ API-delay | ❌ $0.01/call | ⚠️ Low | ✅ 99% |

## References

- [browser-use](https://github.com/browser-use/browser-use)
- [Playwright Python](https://playwright.dev/python/)
- [ECS Run Task API](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ecs-run-task.html)
