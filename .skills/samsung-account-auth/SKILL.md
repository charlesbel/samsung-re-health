---
name: samsung-account-auth
description: Bootstrap shared Samsung Account authentication safely.
version: 0.3.0
author: Charles Bel, Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [samsung, authentication, oauth, master-state, health, smart-home]
---

# Samsung Account Authentication

Use this skill to create or repair the neutral `master-state-v1` shared by `samsung-re-find` and `samsung-re-health`. Either package can perform the complete interactive login independently; choose one installed CLI and use it consistently for the four account commands below.

This is an unofficial reverse-engineered flow and is not affiliated with Samsung.

## When to use

- First-time online setup.
- Repairing revoked or expired master credentials.
- Checking non-secret master-state readiness.

## Prerequisites

- Either `samsung-re-find` or `samsung-re-health` installed.
- A Linux desktop with `xdg-mime` for automatic callback capture. Other platforms currently need an independently configured private handler for the exact `ms-app://` callback.
- A browser for the user to sign in on Samsung's own page.

Never ask for or expose a password, second factor, callback URI, token, cookie, or state-file content.

## Procedure

The command names are identical. Replace `<cli>` with either `samsung-re-find` or `samsung-re-health`:

```bash
<cli> install-handler
<cli> auth-start --country us --locale en-US
# Open the login_url from the JSON response and complete the Samsung-hosted login.
<cli> auth-complete
<cli> account-status
```

`auth-start` creates private PKCE state that expires after 15 minutes. `auth-complete` consumes the captured callback and creates the shared master state. `account-status` reports only booleans and the schema version, never credential values.

After account setup, initialize the selected service:

```bash
samsung-re-find status
# or
samsung-re-health init
samsung-re-health status
```

## Shared-state contract

- Persistent master: `samsung-account/master.json`.
- Transient login state: `samsung-account/pending.json`.
- One-shot callback: `samsung-account/redirect.uri`.
- All three resolve under the same platform account directory, or beside a custom master path.
- Find and Health keep service-specific tokens and data in separate state directories.
- Health bootstrap does not request or store Find or IoT tokens.

The master is JSON protected by private filesystem permissions; it is not encrypted at rest. Anyone able to read it may be able to reuse the Samsung session.

## Pitfalls

- If the pending state expires, restart with `auth-start`.
- Do not paste the login URL or callback into chat, shell history, logs, issues, or CI output.
- Do not copy the master or transient files into a service-specific state directory.
- Installing either callback handler is sufficient because both write the same neutral callback path; the CLI used for `auth-complete` must resolve the same master path.
- Account readiness does not prove that Find devices or Health documents are available for the account.

## Verification

- `account-status` succeeds and returns only `authenticated`, `device_id_present`, `user_id_present`, and `schema_version`.
- The account directory is private and contains no service-specific Find or Health state.
- Run the selected service's own status or initialization command separately; do not infer service availability from master readiness.
