package main

import (
	"fmt"
	"log"
	"net/http"
	"os/exec"
	"strings"
	"sync"
	"time"
)

type QueueItem struct {
	UserID    int64
	Title     string
	Args      []string
	StartedAt time.Time
}

type App struct {
	cfg    Config
	db     *Database
	mu     sync.Mutex
	rtmp   map[int64]string
	queue  map[int64][]QueueItem
	status map[int64]string
}

func newApp(cfg Config, db *Database) *App {
	return &App{cfg: cfg, db: db, rtmp: map[int64]string{}, queue: map[int64][]QueueItem{}, status: map[int64]string{}}
}

func ffmpegVideoArgs(input, rtmp string) []string {
	return []string{"-hide_banner", "-loglevel", "error", "-re", "-i", input, "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency", "-pix_fmt", "yuv420p", "-c:a", "aac", "-f", "flv", rtmp}
}

func (a *App) health(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	_, _ = w.Write([]byte(`{"status":"ok","runtime":"go-2026"}`))
}

func (a *App) streamDryRun(w http.ResponseWriter, r *http.Request) {
	input := strings.TrimSpace(r.URL.Query().Get("input"))
	rtmp := strings.TrimSpace(r.URL.Query().Get("rtmp"))
	if input == "" || rtmp == "" {
		http.Error(w, "input and rtmp query params are required", http.StatusBadRequest)
		return
	}
	cmd := exec.Command("ffmpeg", ffmpegVideoArgs(input, rtmp)...)
	if err := cmd.Start(); err != nil {
		http.Error(w, "ffmpeg start failed: "+err.Error(), http.StatusInternalServerError)
		return
	}
	_ = cmd.Process.Kill()
	_, _ = w.Write([]byte("ffmpeg command validated"))
}

func main() {
	cfg := loadConfig()
	if err := cfg.validate(); err != nil {
		log.Fatal("Missing BOT_TOKEN or MONGO_URL env for deployment parity")
	}

	db := newDB(cfg.MongoURL)
	app := newApp(cfg, db)

	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", app.health)
	mux.HandleFunc("/stream/validate", app.streamDryRun)

	addr := ":" + cfg.Port
	log.Printf("Gojo Satoru Go service listening on %s", addr)
	log.Printf("RTMP base configured: %s", cfg.DefaultRTMPURL)
	if err := http.ListenAndServe(addr, mux); err != nil {
		log.Fatal(fmt.Errorf("server failed: %w", err))
	}
}
