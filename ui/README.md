# RetailPulse KB UI

Static, serverless, single-page web app for searching the RetailPulse knowledge base and submitting feedback.

## Features

- **Search** — semantic search with source filter, top-K
- **Feedback** — 1–5 star rating + free-text comments
- **Live analytics** — results count, query duration
- **Responsive** — works on desktop and mobile

## Architecture

```text
ui/
├── index.html      # Markup
├── style.css       # Styles (dark theme, GitHub-inspired)
└── app.js          # Client logic (vanilla JS, no build step)
```

The UI is intentionally **framework-free** to minimize bundle size and keep deployment simple. No React, no Vue, no build pipeline — just three files deployed to S3 + CloudFront.

## API integration

The UI calls the RetailPulse API via `fetch()` with the API URL configured by:

1. **Build-time**: `window.RETAILPULSE_API_URL` injected by Terraform into `index.html`
2. **Runtime**: read from `<meta name="api-url" content="...">` if present
3. **Dev fallback**: hardcoded `https://api.example.com`

For IAM-authenticated calls (production), the UI must use AWS SDK with SigV4 signing.

## Local development

```bash
# Serve locally
python -m http.server 8000 --directory ui
# Open <http://localhost:8000>
```

## Deployment

The UI bucket (`retailpulse-ui-dev`) is configured for static website hosting. CloudFront in front provides HTTPS.

```bash
# After terraform apply:
aws s3 sync ui/ s3://retailpulse-ui-dev/static/ --delete

# CloudFront will pick up changes within 5 minutes (cache TTL)
# Or invalidate:
aws cloudfront create-invalidation --distribution-id <id> --paths "/static/*"
```
