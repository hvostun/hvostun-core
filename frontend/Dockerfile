FROM node:24-alpine@sha256:a34ab6d7f6f4813f4d0c5469d74685604b962fbdbf5793a7bc7b4998ecb867c8 AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts
COPY tsconfig.json vite.config.ts index.html ./
COPY src src
COPY design/illustrations design/illustrations
RUN npm run typecheck && npm run build

FROM nginxinc/nginx-unprivileged:1.29-alpine@sha256:0c79d56aee561a1d81c63f00eee5fb5fe29279560cdc55e91425133104c7fbe6
USER root
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY docker-entrypoint.d/40-htpasswd.sh /docker-entrypoint.d/40-htpasswd.sh
RUN chmod 0755 /docker-entrypoint.d/40-htpasswd.sh \
 && chown root:root /etc/nginx/conf.d/default.conf /docker-entrypoint.d/40-htpasswd.sh \
 && rm -f /usr/share/nginx/html/*
COPY --from=build --chown=root:root /app/dist /usr/share/nginx/html
USER 101
EXPOSE 8080
