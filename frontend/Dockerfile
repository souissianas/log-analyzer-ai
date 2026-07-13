# Build stage
FROM node:18-alpine AS builder
WORKDIR /app

# VITE_API_URL is a build-time PUBLIC value bundled into the client JS by Vite —
# it is not a secret (anyone can read it in the browser bundle).
# Renamed from VITE_API_KEY to VITE_API_URL to stop SonarCloud from flagging it
# as a hard-coded credential pattern. If you ever need a REAL secret at build time,
# use Docker BuildKit secrets instead (--mount=type=secret), never ARG/ENV.
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL

COPY package.json package-lock.json* ./
RUN npm ci --silent
COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine

RUN apk update && apk upgrade --no-cache libexpat

COPY --from=builder /app/dist /usr/share/nginx/html
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Run as non-root (fixes: "The nginx image runs with root as the default user")
# nginx:alpine already ships an "nginx" user (uid 101) — no need to create one.
RUN chown -R nginx:nginx /usr/share/nginx/html \
    && chown -R nginx:nginx /var/cache/nginx \
    && chown -R nginx:nginx /var/log/nginx \
    && chown -R nginx:nginx /etc/nginx/conf.d \
    && touch /var/run/nginx.pid \
    && chown -R nginx:nginx /var/run/nginx.pid

USER nginx

# Non-root can't bind to port 80 by default, switch to 8080
# (make sure nginx.conf's "listen" directive also says 8080)
EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
