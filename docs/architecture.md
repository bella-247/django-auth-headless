# Architecture

`django-auth-headless` is a Django integration package. It does not contain a
frontend, user interface, user model, database project, or hosting adapter.
The consuming application owns those concerns.

The package composes django-allauth Headless with:

- Environment-backed configuration.
- Database-backed `SocialApp` setup.
- Site and provider verification.
- A structured current-user endpoint.
- Same-site session support.
- Optional cross-domain authorization-code exchange.

## Authentication modes

### Same-site mode

Use Django's session cookie when the frontend and backend are same-site,
including subdomains under a domain controlled by the application. This is the
simplest mode and does not require frontend token storage.

### Separate-host mode

For unrelated hosts, browser cookies are not a dependable transport:

```text
OAuth callback
    → one-time handoff code in URL fragment
    → POST exchange
    → short-lived bearer token
    → Authorization header
```

Handoff codes and access tokens are stored only as hashes. Handoff redemption
is transactionally locked and single-use.

## Configuration boundary

`conf.py` is the only module that reads environment configuration. `build()`
accepts an explicit mapping, so configuration can be tested without mutating
the process environment.

## Design intent

The package adds repetitive Django integration work while leaving allauth
responsible for provider behavior. It does not replace a mature OAuth engine
with a second, incompatible authentication implementation.
