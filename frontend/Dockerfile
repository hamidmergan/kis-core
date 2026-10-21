FROM node:20-alpine AS base

# Install dependencies
FROM base AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
# The npm cache survives between builds, so a changed lockfile only downloads what is new.
RUN --mount=type=cache,target=/root/.npm npm ci || npm install

# Build
FROM base AS builder
WORKDIR /app
ARG BACKEND_URL=http://localhost:8000
ENV BACKEND_URL=$BACKEND_URL
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Next.js reuses its compile cache from the last build, so only changed files are compiled again.
RUN --mount=type=cache,target=/app/.next/cache npm run build

# Production
FROM base AS runner
WORKDIR /app
ENV NODE_ENV=production

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public

# Standalone output
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]
