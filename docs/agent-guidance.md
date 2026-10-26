# Guidance for AI coding agents

This repository welcomes careful contributions from AI-assisted developers.
Authentication, OAuth credentials, cookies, and bearer tokens are
security-sensitive.

## Required workflow

1. Read the README and the relevant document in `docs/`.
2. Inspect existing tests before changing public behavior.
3. Keep provider secrets and real tokens out of code, logs, tests, and commits.
4. Preserve session behavior for same-site deployments.
5. Never move a reusable access token into a URL.
6. Validate configuration at the environment boundary.
7. Add regression tests for authentication and authorization changes.
8. Run Django tests, build, and `git diff --check`.

Do not add a frontend, example application, or hosted-service integration to
this repository. Use the separate
[DjangoOAuth learning project](https://github.com/bella-247/DjangoOAuth) for
end-to-end frontend examples.
