# Authentication Architecture

> **Disclaimer**: `samsung-re-health` is an unofficial, reverse-engineered project and is not affiliated with Samsung Electronics Co., Ltd.

## Overview

`samsung-re-health` utilizes Samsung's OAuth2 and SCSP (Samsung Cloud Service Platform) authentication hierarchy.

Authentication is bootstrapped using a single shared master state file. Either `samsung-re-health` or `samsung-re-find` can perform the initial interactive login independently; Health does not import or require the Find package.

```text
Samsung Account Interactive Login
  (samsung-re-health OR samsung-re-find)
                    │
                    ▼
     Neutral Master State v1 (master.json)
         ┌──────────┴──────────┐
         ▼                     ▼
 samsung-re-find Session  samsung-re-health Session
 (user_state_dir)         (user_state_dir)
         │                     │
         ▼                     ▼
 samsung-re-find CLI/MCP   samsung-re-health CLI/MCP
```

## Token Hierarchy

1. **Master Token (`userauth_token`)**:
   - Stored in `samsung-account/master.json`.
   - Used to request service-specific access tokens.
   - Created atomically by the explicit Health `auth-complete` bootstrap command, or by the equivalent Find flow. Normal Health session initialization only consumes it.
2. **Health OAuth2 Tokens**:
   - `health_access_token` and `health_refresh_token`.
   - Exchanged with the HTTPS Samsung auth endpoint declared by the validated master state, using the Health client ID. The host must satisfy the package allowlist; no fixed regional hostname is assumed.
   - Cached in service-specific `state.json`.
3. **SCSP Cloud Tokens**:
   - `registration_id` registered via `https://play.samsungcloud.com/identity/v1/register`.
   - `cloud_token` issued via `https://play.samsungcloud.com/identity/v1/tokens`.
   - Used for all read requests to Samsung Cloud data endpoints.

## Master State Resolution Order

1. Programmatically injected path in SDK facade `HealthConfig(master_state_path=...)`
2. `--master-state <PATH>` CLI / MCP command-line argument
3. `SAMSUNG_ACCOUNT_MASTER_STATE` environment variable
4. Default shared master path for the current OS
5. Matching legacy Find state for the current OS, used only when the master file is absent

The default and legacy locations intentionally match `samsung-re-find` exactly:

| OS | Master State v1 | Legacy Find state |
|---|---|---|
| Linux | `$XDG_CONFIG_HOME/samsung-account/master.json` (normally `~/.config/samsung-account/master.json`) | `$XDG_CONFIG_HOME/samsung-find/state.json` (normally `~/.config/samsung-find/state.json`) |
| macOS | `~/Library/Application Support/samsung-account/master.json` | `~/Library/Application Support/samsung-find/state.json` |
| Windows | `%APPDATA%\samsung-account\master.json` | `%APPDATA%\samsung-find\state.json` |

Windows uses the roaming `%APPDATA%` root, not local app data. macOS uses `Application Support`; Linux retains `platformdirs`/XDG behavior.

## Independent Interactive Bootstrap

On Linux, Health can install its own private callback handler and complete the full flow without Find:

```bash
samsung-re-health install-handler
samsung-re-health auth-start --country us --locale en-US
# Open the emitted login_url and complete the Samsung-hosted login.
samsung-re-health auth-complete
samsung-re-health account-status
```

`auth-start` performs a no-redirect entry-point request, creates a PKCE verifier and encrypted `svcParam`, and writes private `pending.json`. The browser callback must exactly match the configured `REDIRECT_URI`. `auth-complete` securely consumes the captured `redirect.uri`, rejects pending flows older than 15 minutes, decrypts the callback, performs the no-redirect master authentication exchange, validates the final Samsung URL, and atomically writes `master-state-v1`.

The transient files live beside the master state under `samsung-account/`:

- `master.json`: neutral persistent `master-state-v1` (`0600` on POSIX).
- `pending.json`: temporary PKCE/login state, valid for at most 15 minutes.
- `redirect.uri`: one-shot captured callback consumed by `auth-complete`.

None of these transient files is written to Health-derived state or Find-derived state. The Health bootstrap does not request or persist Find or IoT tokens.

When adopting Master State v1, Health only stamps a previously missing generation onto an empty derived state. If pre-0.7 Health authentication, identity, or registration state already exists without a generation, it is cleared and reinitialized before the new generation is persisted; cached credentials are never silently adopted across unknown lineage.
