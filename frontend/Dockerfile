# Stage 1: build the Vite app
FROM node:20-alpine AS build

WORKDIR /app

# Build-time env: Vite reads VITE_* at build. /api is the default
# Nginx reverse-proxy path. Override at build time if needed.
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

COPY package.json package-lock.json* ./
RUN npm install --no-audit --no-fund

COPY . .
RUN npm run build

# Stage 2: serve the static build with Nginx
FROM nginx:1.27-alpine

# Replace the default nginx config with one that reverse-proxies /api
# to the backend service on the internal Docker network.
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -qO- http://localhost:3000/ || exit 1

CMD ["nginx", "-g", "daemon off;"]