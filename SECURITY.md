# Security Policy

## Supported Versions

Only the latest version on the `main` branch of Horolog receives security updates.

| Version | Supported          |
| ------- | ------------------ |
| `0.1.x` | :white_check_mark: |
| `< 0.1` | :x:                |

---

## Reporting a Vulnerability

We take the security of Horolog seriously. Because Horolog interacts with personal calendar feeds and local/remote LLM endpoints, prompt injection and calendar data boundary protection are key concerns.

If you discover a security vulnerability in Horolog, please report it responsibly:

1. **Do not create a public GitHub issue** for security vulnerabilities.
2. Email your report to the maintainers or report via GitHub Security Advisories.
3. Include detailed steps to reproduce the issue, proof-of-concept code, and the potential impact of the vulnerability.

We will acknowledge receipt of your report within 48 hours and provide status updates as we work on a resolution.

---

## Threat Model & Security Considerations

### 1. Single-User Self-Hosting & Authentication
- Horolog is designed by default as an unauthenticated single-user service intended to run on `localhost` or within an isolated private network / container stack.
- **For remote or team access**: Always place Horolog behind an authenticating reverse proxy (e.g. Tailscale Auth, Cloudflare Access, OAuth2-Proxy, Authelia, or Nginx with HTTP basic/OIDC auth). Do not expose port `8000` or `3000` directly to the public Internet without an identity provider.

### 2. LLM Boundary & Calendar Write Protection
- The natural language capture feature uses grammar-constrained decoding to parse user text into candidate `IntentDraft` models.
- The LLM has **no write access** to calendar stores, CalDAV servers, or database rows directly. All outputs pass through strict Pydantic model validation and the deterministic placement engine before creating scheduled blocks.

### 3. ICS / CalDAV Credentials
- CalDAV passwords and ICS subscription URLs are stored in local database instances. Ensure your database storage directory (`./data/` or SQLite file) has restricted filesystem permissions (`0600` / `0700`).
