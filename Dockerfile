FROM golang:1.24-alpine AS builder
WORKDIR /app
COPY go.mod .
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o /gojo-bot .

FROM alpine:3.21
RUN apk add --no-cache ffmpeg ca-certificates tzdata
WORKDIR /app
COPY --from=builder /gojo-bot /app/gojo-bot
COPY cookies.txt /app/cookies.txt
ENV TZ=UTC
CMD ["/app/gojo-bot"]
