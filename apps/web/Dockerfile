FROM node:20-alpine AS dependencies
WORKDIR /app
COPY package*.json ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund

FROM node:20-alpine AS builder
WORKDIR /app
ARG API_INTERNAL_BASE=http://api:8000
ENV NEXT_TELEMETRY_DISABLED=1 \
    API_INTERNAL_BASE=${API_INTERNAL_BASE}
COPY --from=dependencies /app/node_modules ./node_modules
COPY . .
RUN mkdir -p public && npm run build

FROM node:20-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    API_INTERNAL_BASE=http://api:8000 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
RUN addgroup -S lucyworks && adduser -S lucyworks -G lucyworks
COPY --from=builder --chown=lucyworks:lucyworks /app/public ./public
COPY --from=builder --chown=lucyworks:lucyworks /app/.next/standalone ./
COPY --from=builder --chown=lucyworks:lucyworks /app/.next/static ./.next/static
USER lucyworks
EXPOSE 3000
CMD ["node", "server.js"]
