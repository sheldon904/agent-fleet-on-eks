package main

import (
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"
)

// Config holds all runtime configuration, sourced from environment variables.
// Secret values may be provided directly (VAR) or via a file path (VAR_FILE), which is how
// the AWS Secrets Store CSI driver surfaces Secrets Manager values on Kubernetes.
type Config struct {
	Port           string
	HMACSecret     []byte
	RequestTimeout time.Duration

	Ntfy     NtfyConfig
	Telegram TelegramConfig
}

// NtfyConfig configures the ntfy target.
type NtfyConfig struct {
	BaseURL string
	Topic   string
	Token   string
}

// Enabled reports whether the ntfy target has enough config to be used.
func (c NtfyConfig) Enabled() bool { return c.BaseURL != "" && c.Topic != "" }

// TelegramConfig configures the Telegram target.
type TelegramConfig struct {
	BotToken string
	ChatID   string
}

// Enabled reports whether the Telegram target has enough config to be used.
func (c TelegramConfig) Enabled() bool { return c.BotToken != "" && c.ChatID != "" }

// LoadConfig builds a Config from the environment, returning an error only for genuinely
// required values (the HMAC secret). Targets are optional and simply stay disabled.
func LoadConfig() (Config, error) {
	cfg := Config{
		Port:           getEnv("PORT", "8080"),
		RequestTimeout: getDurationEnv("REQUEST_TIMEOUT", 5*time.Second),
	}

	secret, err := getSecret("HMAC_SECRET")
	if err != nil {
		return Config{}, err
	}
	if len(secret) == 0 {
		return Config{}, fmt.Errorf("HMAC_SECRET (or HMAC_SECRET_FILE) is required")
	}
	cfg.HMACSecret = secret

	cfg.Ntfy = NtfyConfig{
		BaseURL: strings.TrimRight(getEnv("NTFY_URL", ""), "/"),
		Topic:   getEnv("NTFY_TOPIC", ""),
	}
	if tok, _ := getSecret("NTFY_TOKEN"); len(tok) > 0 {
		cfg.Ntfy.Token = string(tok)
	}

	cfg.Telegram = TelegramConfig{ChatID: getEnv("TELEGRAM_CHAT_ID", "")}
	if tok, _ := getSecret("TELEGRAM_BOT_TOKEN"); len(tok) > 0 {
		cfg.Telegram.BotToken = string(tok)
	}

	return cfg, nil
}

// AnyTargetEnabled reports whether at least one notification target is configured.
func (c Config) AnyTargetEnabled() bool {
	return c.Ntfy.Enabled() || c.Telegram.Enabled()
}

func getEnv(key, def string) string {
	if v, ok := os.LookupEnv(key); ok {
		return v
	}
	return def
}

func getDurationEnv(key string, def time.Duration) time.Duration {
	v, ok := os.LookupEnv(key)
	if !ok {
		return def
	}
	if d, err := time.ParseDuration(v); err == nil {
		return d
	}
	if secs, err := strconv.Atoi(v); err == nil {
		return time.Duration(secs) * time.Second
	}
	return def
}

// getSecret reads KEY directly, or the file referenced by KEY_FILE (a CSI-mounted secret).
// KEY_FILE takes precedence so a Kubernetes deployment can mount secrets as files.
func getSecret(key string) ([]byte, error) {
	if path, ok := os.LookupEnv(key + "_FILE"); ok && path != "" {
		b, err := os.ReadFile(path)
		if err != nil {
			return nil, fmt.Errorf("reading %s_FILE: %w", key, err)
		}
		return []byte(strings.TrimSpace(string(b))), nil
	}
	if v, ok := os.LookupEnv(key); ok {
		return []byte(v), nil
	}
	return nil, nil
}
