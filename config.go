package main

import (
	"errors"
	"os"
	"strconv"
	"strings"
)

var ErrConfig = errors.New("missing required configuration")

type Config struct {
	OwnerID        int64
	BotToken       string
	DefaultRTMPURL string
	LoggerID       int64
	MongoURL       string
	Port           string
}

func int64Env(name string, def int64) int64 {
	v := strings.TrimSpace(os.Getenv(name))
	if v == "" {
		return def
	}
	n, err := strconv.ParseInt(v, 10, 64)
	if err != nil {
		return def
	}
	return n
}

func loadConfig() Config {
	cfg := Config{
		OwnerID:        int64Env("OWNER_ID", 0),
		BotToken:       strings.TrimSpace(os.Getenv("BOT_TOKEN")),
		DefaultRTMPURL: strings.TrimSpace(os.Getenv("DEFAULT_RTMP_URL")),
		LoggerID:       int64Env("LOGGER_ID", 0),
		MongoURL:       strings.TrimSpace(os.Getenv("MONGO_URL")),
		Port:           strings.TrimSpace(os.Getenv("PORT")),
	}
	if cfg.DefaultRTMPURL == "" {
		cfg.DefaultRTMPURL = "rtmps://dc5-1.rtmp.t.me/s/"
	}
	if cfg.Port == "" {
		cfg.Port = "8080"
	}
	return cfg
}

func (c Config) validate() error {
	if c.BotToken == "" || c.MongoURL == "" {
		return ErrConfig
	}
	return nil
}
