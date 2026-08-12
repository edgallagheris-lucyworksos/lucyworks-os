# Codespace resume freshness fix v32

## Defect

A resumed Codespace could keep serving an older LucyWorks build because the startup script treated healthy listeners on ports 3000 and 8000 as sufficient proof that the environment was current.

That allowed an old frontend/API process to survive while `origin/main` had advanced.

## Fix

On Codespace startup or attach:

1. If the checkout is on `main`, fetch `origin/main`.
2. If the working tree is clean and the local commit is an ancestor of `origin/main`, fast-forward automatically.
3. Never overwrite dirty or divergent local work.
4. Record the exact commit served by the running processes in `/tmp/lucyworks-running-sha`.
5. Reuse healthy listeners only when that recorded commit exactly matches the checked-out commit.
6. Otherwise kill stale listeners and restart both API and web from the current checkout.
7. Print the running commit and direct operational links after startup.

## Acceptance

A Codespace resumed after `main` has advanced must not silently serve the previous build.
