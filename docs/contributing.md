# Contributing

Thank you for contributing to `django-auth-headless`.

## Before opening an issue

Include the package version, Python/Django versions, provider, deployment
mode, exact failing command or endpoint, sanitized `verify_oauth` output, and
a minimal reproduction when possible. Never include client secrets, access
tokens, cookies, or personal data.

## Development

```bash
uv sync --group dev
uv run python manage.py test
uv build
```

Changes should include tests and documentation when they change public
configuration, commands, endpoints, or security behavior.

## Pull requests

Keep pull requests focused. Explain the user problem, behavior before and
after, compatibility and migration impact, and security implications. Run
tests, build the distributions, and check the staged diff for secrets.
