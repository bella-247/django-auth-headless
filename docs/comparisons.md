# Comparison with existing approaches

`django-auth-headless` is an integration layer, not a replacement for every
authentication library. Its goal is to make the common Django OAuth setup
path easier and more diagnosable.

| Approach | What it provides | What this project adds |
| --- | --- | --- |
| `django-allauth` Headless | A capable JSON-first authentication engine | Guided provider setup, Site/SocialApp verification, composed settings, and optional cross-domain handoff |
| `dj-rest-auth` | REST endpoints around common allauth flows | A browser redirect flow and deployment-mode guidance without requiring provider-specific token acquisition in the frontend |
| `django-oauth-toolkit` | An OAuth 2.0 authorization server | A smaller integration for applications where users sign in with external providers, not a full authorization server |
| `social-auth-app-django` | Social authentication pipelines | A modern Headless-oriented configuration and verification path |
| Hosted services such as Auth0, Clerk, or Supabase | Managed identity and cross-domain flows | Self-hosted users and data in the Django application without a required SaaS dependency |

These approaches overlap but are not interchangeable. This comparison is
scoped to the setup and deployment problem this project addresses.

## Problems addressed

### Configuration glue

The setup and verification commands handle the Site, database-backed
SocialApp, environment variables, and Headless configuration endpoint.

### Deployment differences

Same-site deployments use Django sessions. Unrelated frontend and backend
hosts use a one-time authorization-code exchange and bearer headers.

### Security mistakes

The package keeps provider secrets on Django, hashes handoff codes and access
tokens, prevents code reuse, and documents the boundaries that CORS and
cookies cannot cross.

## What it does not solve

The package does not create Google Cloud projects, manage DNS, replace
application authorization, or decide tenant onboarding rules.
