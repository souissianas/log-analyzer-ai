# Build stage
FROM node:18-alpine AS builder
WORKDIR /app
ARG VITE_API_KEY=
ENV VITE_API_KEY=$VITE_API_KEY
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
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
