# syntax=docker/dockerfile:1
# Versions are pinned so the image can be rebuilt identically (WBS Day 15).
FROM golang:1.22.12-alpine3.21 AS builder
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download && go mod verify
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/api ./cmd/api

FROM alpine:3.21.3
RUN apk add --no-cache ca-certificates tzdata wget \
    && addgroup -S app && adduser -S -G app app
WORKDIR /app
COPY --from=builder /out/api /app/api
COPY serving_data /app/serving_data
USER app
ENV PORT=8080 DATA_DIR=/app/serving_data
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
  CMD wget -qO- http://127.0.0.1:8080/healthz >/dev/null || exit 1
ENTRYPOINT ["/app/api"]
