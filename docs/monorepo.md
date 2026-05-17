# LucyWorksOS Monorepo

Structure:
- apps/api FastAPI canonical backend
- apps/web Next.js hospital operations dashboard
- packages/shared shared TypeScript constants/schemas
- data/seed hospital_snapshot.json
- scripts run/check helpers

Ports:
- API: 8000
- Web: 3000

URLs:
- http://localhost:8000/api/health
- http://localhost:3000/hospital-board
