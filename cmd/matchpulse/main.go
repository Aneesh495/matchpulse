package main

import (
	"context"
	"flag"
	"github.com/Aneesh495/matchpulse-football/internal/server"
	"log"
	"net"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"
)

func main() {
	addr := flag.String("addr", "127.0.0.1:8777", "HTTP listen address")
	db := flag.String("db", "runtime/matchpulse.db", "SQLite database")
	assets := flag.String("assets", "dist", "compiled web directory")
	python := flag.String("python", "python3", "Python 3.13+ executable")
	flag.Parse()
	host, _, err := net.SplitHostPort(*addr)
	if err != nil {
		log.Fatal(err)
	}
	token := os.Getenv("MATCHPULSE_API_TOKEN")
	if host != "127.0.0.1" && host != "localhost" && host != "::1" && token == "" {
		log.Fatal("non-loopback serving requires MATCHPULSE_API_TOKEN")
	}
	worker := server.NewWorker(*python, *db)
	defer worker.Close()
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	_, err = worker.Call(ctx, "state", map[string]any{})
	cancel()
	if err != nil {
		log.Fatal(err)
	}
	app := &server.Server{Engine: worker, Assets: *assets, Token: token}
	srv := &http.Server{Addr: *addr, Handler: app.Handler(), ReadHeaderTimeout: 5 * time.Second, IdleTimeout: 45 * time.Second, MaxHeaderBytes: 32768}
	stop := make(chan os.Signal, 1)
	signal.Notify(stop, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		<-stop
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		srv.Shutdown(ctx)
	}()
	log.Printf("Matchpulse local research terminal: http://%s", *addr)
	if err = srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatal(err)
	}
}
