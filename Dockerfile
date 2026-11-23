FROM node:22-slim

WORKDIR /app

RUN corepack enable && corepack prepare pnpm@9.15.9 --activate

COPY package.json pnpm-lock.yaml ./
COPY client/package.json ./client/

RUN pnpm install --frozen-lockfile
RUN pnpm --dir client install --frozen-lockfile

COPY . .

RUN pnpm run build

ENV NODE_ENV=production
ENV PORT=8080
EXPOSE 8080

CMD ["pnpm", "exec", "tsx", "server/index.ts"]
