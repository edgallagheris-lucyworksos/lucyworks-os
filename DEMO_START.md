# LucyWorks OS — Working Build Start

This is the current working build of the LucyWorks OS operating spine.

It is not a throwaway demo and it is not being claimed as a finished hospital-grade system. The current job is to make the working build run cleanly, read clearly, and expose the right operating logic.

## Codespaces first run

The devcontainer installs backend and frontend dependencies automatically when the Codespace is created.

If needed, run:

```bash
npm run backend:install && npm run frontend:install
```

## Check build

```bash
npm run check
```

This runs:

```bash
npm run backend:smoke
npm run backend:safety
npm run frontend:build
```

## Start the working build

Use two terminals.

### Terminal 1 — backend

```bash
npm run backend:run
```

Backend port:

```text
8000
```

### Terminal 2 — frontend

```bash
npm run frontend:run
```

Frontend port:

```text
3000
```

Open the forwarded `3000` port.

## Main operating path

Start here:

```text
/login
```

Then open:

```text
/workspace
/system
/pulse
/command
/episodes/EP-1042
```

`EP-1042` is seeded data used to exercise the current build path. It is not the product boundary.

## What to check visually

- `/system` explains the operating spine.
- `/pulse` gives risk interpretation and next pressure source.
- `/command` gives hospital control state and lead action.
- `/episodes/EP-1042` gives case intelligence, blockers, warnings and next owner.
- `/rooms` room buttons should update state.
- `/mail` replies should create message entries.

## If something fails

Copy the first red error only:

```text
Traceback
AssertionError
Type error
Build failed
ERROR
FAILED
```
