# Deployment and security

## Same-site frontend and backend

For `app.example.com` and `api.example.com`:

```dotenv
DJANGO_SESSION_COOKIE_DOMAIN=.example.com
DJANGO_SESSION_COOKIE_SECURE=True
DJANGO_CSRF_COOKIE_SECURE=True
DJANGO_CORS_ALLOWED_ORIGINS=https://app.example.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://app.example.com
```

Use a parent domain controlled by the application.

## Unrelated frontend and backend

For unrelated hosts, use the cross-domain authorization-code exchange. Do not
try to bridge unrelated domains with a broad cookie domain. Use HTTPS and
restrict CORS to the exact frontend origin.

## Token handling

- Handoff codes expire after five minutes.
- Handoff codes are single-use.
- Access tokens are stored hashed.
- Access tokens have a configured lifetime.
- Access tokens can be revoked.
- Frontends should keep access tokens in memory.
- Never put access tokens in URLs, localStorage, or sessionStorage.
- Do not log request authorization headers.

## Production checklist

- Set `DEBUG=False`.
- Use a unique secret key from a secret manager.
- Configure exact allowed hosts.
- Use HTTPS for frontend, backend, and OAuth callbacks.
- Enable secure cookies when using sessions.
- Configure exact CORS and CSRF origins.
- Use a production email backend.
- Run `python manage.py check --deploy`.
- Rotate provider credentials if they were exposed.
