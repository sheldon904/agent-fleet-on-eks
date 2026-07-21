# syntax=docker/dockerfile:1

# ---- build ----
FROM golang:1.23 AS build
WORKDIR /src
# No third-party deps: go.mod alone is enough and this layer caches well.
COPY go.mod ./
RUN go mod download
COPY . .
# Static, stripped binary so it runs on distroless with no libc.
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/notify-bridge .

# ---- runtime ----
FROM gcr.io/distroless/static:nonroot
COPY --from=build /out/notify-bridge /notify-bridge
# Numeric UID (distroless "nonroot" = 65532) so Kubernetes runAsNonRoot can verify it.
USER 65532:65532
EXPOSE 8080
ENTRYPOINT ["/notify-bridge"]
