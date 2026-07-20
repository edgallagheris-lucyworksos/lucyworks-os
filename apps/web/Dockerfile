FROM node:20-alpine AS dependencies
WORKDIR /repo/apps/web
COPY apps/web/package*.json ./
RUN npm install --no-audit --no-fund

FROM node:20-alpine AS builder
WORKDIR /repo
ARG API_INTERNAL_BASE=http://api:8000
ENV NEXT_TELEMETRY_DISABLED=1 \
    API_INTERNAL_BASE=${API_INTERNAL_BASE}
COPY --from=dependencies /repo/apps/web/node_modules ./apps/web/node_modules
COPY apps/web ./apps/web
COPY packages/shared ./packages/shared
WORKDIR /repo/apps/web
RUN mkdir -p public && npm run build

FROM node:20-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    API_INTERNAL_BASE=http://api:8000 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
RUN addgroup -S lucyworks && adduser -S lucyworks -G lucyworks
COPY --from=builder --chown=lucyworks:lucyworks /repo/apps/web/public ./apps/web/public
COPY --from=builder --chown=lucyworks:lucyworks /repo/apps/web/.next/standalone ./
COPY --from=builder --chown=lucyworks:lucyworks /repo/apps/web/.next/static ./apps/web/.next/static
USER lucyworks
EXPOSE 3000
CMD ["sh", "-c", "if [ -f /app/apps/web/server.js ]; then exec node /app/apps/web/server.js; else exec node /app/server.js; fi"]
