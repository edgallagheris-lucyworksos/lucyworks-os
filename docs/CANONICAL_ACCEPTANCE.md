# Canonical acceptance

LucyWorksOS uses one mandatory repository acceptance command:

```bash
npm run check
```

The `Canonical Monorepo Acceptance` GitHub Actions workflow runs this command for every pull request and every push to `main`, and can also be started manually.

A change is acceptable only when the canonical architecture checks, API smoke tests, shared-package checks, and production web build all pass.

The active product implementation remains `apps/web` plus `apps/api`; top-level `frontend/` and `backend/` must not be restored.
