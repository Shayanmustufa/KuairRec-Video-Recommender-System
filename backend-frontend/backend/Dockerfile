# Build stage
FROM golang:1.22-alpine AS builder

WORKDIR /app

RUN apk add --no-cache git gcc musl-dev

COPY go.mod ./
RUN go mod download

COPY . .

RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o /app/api ./cmd/api

# Final runtime stage
FROM alpine:3.19

WORKDIR /app

RUN apk --no-cache add ca-certificates tzdata

COPY --from=builder /app/api /app/api
COPY --from=builder /app/serving_data /app/serving_data

ENV PORT=8080
ENV DATA_DIR=/app/serving_data

EXPOSE 8080

CMD ["/app/api"]
