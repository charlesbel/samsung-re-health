# Authentication Architecture

## Overview

Samsung Health Cloud utilizes Samsung's OAuth2 and SCSP (Samsung Cloud Service Platform) authentication hierarchy.

Authentication is bootstrapped using a single shared master state file created during initial interactive login with Samsung Find.

```text
Samsung Account Interactive Login (Samsung Find)
                    │
                    ▼
     Neutral Master State v1 (master.json)
         ┌──────────┴──────────┐
         ▼                     ▼
 Samsung Find Session   Samsung Health Session
 (user_state_dir)       (user_state_dir)
         │                     │
         ▼                     ▼
 Samsung Find SDK/CLI/MCP  Samsung Health SDK/CLI/MCP
```

## Token Hierarchy

1. **Master Token (`userauth_token`)**:
   - Stored in `samsung-account/master.json`.
   - Used to request service-specific access tokens.
   - Strictly read-only for `samsung-health-cloud`.
2. **Health OAuth2 Tokens**:
   - `health_access_token` and `health_refresh_token`.
   - Exchanged with `https://eu-auth2.samsungosp.com/auth/oauth2/token` using the Health client ID.
   - Cached in service-specific `state.json`.
3. **SCSP Cloud Tokens**:
   - `registration_id` registered via `https://play.samsungcloud.com/identity/v1/register`.
   - `cloud_token` issued via `https://play.samsungcloud.com/identity/v1/tokens`.
   - Used for all read requests to Samsung Cloud data endpoints.

## Master State Resolution Order

1. Programmatically injected path in SDK facade `HealthConfig(master_state_path=...)`
2. `--master-state <PATH>` CLI / MCP command-line argument
3. `SAMSUNG_ACCOUNT_MASTER_STATE` environment variable
4. Default OS user config path: `platformdirs.user_config_dir("samsung-account") / "master.json"`
5. Legacy fallback path: `~/.config/samsung-find/state.json`
