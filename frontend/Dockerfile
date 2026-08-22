FROM registry.cloudbility.com.cn/charmirror/node:24.16.0-bookworm-slim AS dev
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]

FROM registry.cloudbility.com.cn/charmirror/node:24.16.0-bookworm-slim AS builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

FROM registry.cloudbility.com.cn/charmirror/nginx@sha256:fafd5f55296511cd0f1c991efa0cb85f323449bf643f3b6d760c6542f020d6e5 AS prod
COPY frontend/nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/frontend/dist /usr/share/nginx/html
EXPOSE 80
