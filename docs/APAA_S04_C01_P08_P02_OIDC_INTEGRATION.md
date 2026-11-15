# APAA-S04-C01-P08-P02 — Streamlit OIDC Integration

Status: **OIDC login integration added; provider configuration and live login test pending**

Dependency baseline: `streamlit[auth]>=1.45,<2.0` (includes Authlib support required by Streamlit OIDC).

## What was added

- Optional native Streamlit OIDC login using `st.login()`, `st.user`, and `st.logout()`.
- A strict adapter maps only the trusted `iss` and `sub` claims into a Principal.
- The adapter requires an authenticated state, non-empty issuer and subject, numeric expiration and issued-at timestamps, and rejects expired or future-issued identities (with bounded clock skew).
- Set `[apaa].require_auth = true` to make the app stop unless OIDC is configured and the user is logged in.
- Without that setting, the app remains in local prototype mode and displays a warning. Do not expose that mode publicly.

## Configure a provider

Create an OIDC client with your chosen provider (for example Google Identity) and set its authorized redirect URI to your actual app URL plus `/oauth2callback`. For local Streamlit, the default is `http://localhost:8501/oauth2callback`.

Create `.streamlit/secrets.toml` locally (never commit it):

```toml
[auth]
redirect_uri = "http://localhost:8501/oauth2callback"
cookie_secret = "REPLACE_WITH_A_LONG_RANDOM_SECRET"
client_id = "REPLACE_WITH_OIDC_CLIENT_ID"
client_secret = "REPLACE_WITH_OIDC_CLIENT_SECRET"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"

[apaa]
require_auth = true
```

For another provider, replace `server_metadata_url` with that provider's official OIDC discovery URL and use its issued client credentials. Keep tokens and secrets out of source control, UI, and logs.

## Local secret generation

Generate a cookie secret locally with Python:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Copy the output into `cookie_secret` in your local secrets file. Do not paste the value into GitHub or this chat.

## Security limitations

- Streamlit OIDC authenticates identity; it does not implement per-project authorization by itself.
- Project records are not yet bound to owner subjects. That is the next P08 step.
- Live provider redirect, cookie behavior, logout, and two-browser session tests still need to be performed in a configured deployment.
- The local prototype mode remains unauthenticated for automated tests and local development. Never deploy publicly with `require_auth = false`.
- Do not expose ID/access tokens; the default configuration does not expose tokens.

## Safety

No API billing provider, paid model, payment, purchase, trading, shell, browser, filesystem, email, or device execution capability is enabled.
