FROM node:20-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

ARG VITE_API_BASE=/api
ENV VITE_API_BASE=${VITE_API_BASE}

RUN npm run build

FROM alpine:3.20

WORKDIR /opt

RUN adduser -D -u 10001 appuser

COPY --from=build /app/dist /opt/dist
RUN chown -R appuser:appuser /opt/dist

USER appuser

CMD ["/bin/sh", "-c", "cp -r /opt/dist/* /out/ && sleep infinity"]
