package server

import (
	"context"
	"encoding/csv"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"sync/atomic"
	"time"
)

type Backend interface {
	Call(context.Context, string, any) (json.RawMessage, error)
}

type Server struct {
	Engine  Backend
	Assets  string
	Token   string
	clients atomic.Int64
}

func (s *Server) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /api/health", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, 200, map[string]any{"status": "ok", "mode": "research", "licensed_live": false})
	})
	mux.HandleFunc("GET /api/state", s.query("state"))
	mux.HandleFunc("GET /api/matches", s.query("matches"))
	mux.HandleFunc("GET /api/coverage", s.query("coverage"))
	mux.HandleFunc("GET /api/ticker", s.query("ticker"))
	mux.HandleFunc("GET /api/matches/{id}", s.query("match"))
	mux.HandleFunc("GET /api/players/{id}/history", s.query("history"))
	mux.HandleFunc("GET /api/events", s.events)
	mux.HandleFunc("GET /api/export.csv", s.export)
	mux.HandleFunc("POST /api/replay/step", s.mutate("step"))
	mux.HandleFunc("POST /api/ingest", s.mutate("ingest"))
	mux.HandleFunc("POST /api/deals", s.mutate("deal"))
	mux.Handle("/", http.FileServer(http.Dir(s.Assets)))
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Content-Type-Options", "nosniff")
		w.Header().Set("Referrer-Policy", "no-referrer")
		w.Header().Set("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
		w.Header().Set("Cache-Control", "no-store")
		if s.Token != "" && strings.HasPrefix(r.URL.Path, "/api/") && r.Header.Get("Authorization") != "Bearer "+s.Token {
			writeJSON(w, 401, map[string]string{"error": "authentication required"})
			return
		}
		if r.Method == "POST" {
			if origin := r.Header.Get("Origin"); origin != "" {
				parsed, err := url.Parse(origin)
				if err != nil || parsed.Host != r.Host {
					writeJSON(w, 403, map[string]string{"error": "cross-origin mutation denied"})
					return
				}
			}
			if r.Header.Get("Content-Type") != "application/json" {
				writeJSON(w, 415, map[string]string{"error": "application/json required"})
				return
			}
		}
		mux.ServeHTTP(w, r)
	})
}

func writeJSON(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(value)
}

func (s *Server) call(w http.ResponseWriter, r *http.Request, op string, args any) {
	ctx, cancel := context.WithTimeout(r.Context(), 10*time.Second)
	defer cancel()
	data, err := s.Engine.Call(ctx, op, args)
	if err != nil {
		code := 400
		if errors.Is(err, ErrBusy) {
			code = 503
		}
		if errors.Is(err, context.DeadlineExceeded) {
			code = 504
		}
		writeJSON(w, code, map[string]string{"error": err.Error()})
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.Write(data)
}

func (s *Server) query(op string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		args := map[string]any{}
		if id := r.PathValue("id"); id != "" {
			args["id"] = id
		}
		if v := r.URL.Query().Get("version"); v != "" {
			n, err := strconv.Atoi(v)
			if err != nil || n < 1 {
				writeJSON(w, 400, map[string]string{"error": "invalid version"})
				return
			}
			args["version"] = n
		}
		if t := r.URL.Query().Get("as_of"); t != "" {
			args["as_of"] = t
		}
		s.call(w, r, op, args)
	}
}

func (s *Server) mutate(op string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		r.Body = http.MaxBytesReader(w, r.Body, 1024*1024)
		defer r.Body.Close()
		var args map[string]any
		decoder := json.NewDecoder(r.Body)
		if err := decoder.Decode(&args); err != nil {
			writeJSON(w, 400, map[string]string{"error": "invalid or oversized JSON"})
			return
		}
		var extra any
		if err := decoder.Decode(&extra); err == nil {
			writeJSON(w, 400, map[string]string{"error": "one JSON object required"})
			return
		}
		if args == nil {
			writeJSON(w, 400, map[string]string{"error": "object required"})
			return
		}
		s.call(w, r, op, args)
	}
}

func (s *Server) events(w http.ResponseWriter, r *http.Request) {
	if s.clients.Add(1) > 128 {
		s.clients.Add(-1)
		writeJSON(w, 503, map[string]string{"error": "stream capacity reached"})
		return
	}
	defer s.clients.Add(-1)
	after := int64(0)
	if h := r.Header.Get("Last-Event-ID"); h != "" {
		n, err := strconv.ParseInt(h, 10, 64)
		if err != nil || n < 0 {
			writeJSON(w, 400, map[string]string{"error": "invalid stream cursor"})
			return
		}
		after = n
	}
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("X-Accel-Buffering", "no")
	control := http.NewResponseController(w)
	send := func(id int64, event string, data []byte) error {
		control.SetWriteDeadline(time.Now().Add(5 * time.Second))
		if _, err := fmt.Fprintf(w, "id: %d\nevent: %s\ndata: %s\n\n", id, event, data); err != nil {
			return err
		}
		return control.Flush()
	}
	ctx, cancel := context.WithTimeout(r.Context(), 5*time.Second)
	initial, err := s.Engine.Call(ctx, "state", map[string]any{})
	cancel()
	if err != nil {
		return
	}
	var head struct {
		Seq int64 `json:"seq"`
	}
	json.Unmarshal(initial, &head)
	if after == 0 || after > head.Seq {
		after = head.Seq
		if send(after, "recovery", initial) != nil {
			return
		}
	}
	ticker := time.NewTicker(250 * time.Millisecond)
	defer ticker.Stop()
	heartbeat := time.NewTicker(15 * time.Second)
	defer heartbeat.Stop()
	for {
		select {
		case <-r.Context().Done():
			return
		case <-heartbeat.C:
			control.SetWriteDeadline(time.Now().Add(5 * time.Second))
			if _, err = fmt.Fprint(w, ": heartbeat\n\n"); err != nil {
				return
			}
			if control.Flush() != nil {
				return
			}
		case <-ticker.C:
			ctx, cancel := context.WithTimeout(r.Context(), 5*time.Second)
			data, err := s.Engine.Call(ctx, "stream", map[string]any{"after": after, "limit": 64})
			cancel()
			if err != nil {
				return
			}
			var records []struct {
				Seq int64 `json:"seq"`
			}
			var raw []json.RawMessage
			if json.Unmarshal(data, &records) != nil || json.Unmarshal(data, &raw) != nil {
				return
			}
			for i, record := range records {
				if record.Seq <= after {
					return
				}
				if send(record.Seq, "update", raw[i]) != nil {
					return
				}
				after = record.Seq
			}
		}
	}
}

func (s *Server) export(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(r.Context(), 10*time.Second)
	defer cancel()
	data, err := s.Engine.Call(ctx, "ticker", map[string]any{})
	if err != nil {
		writeJSON(w, 500, map[string]string{"error": err.Error()})
		return
	}
	var rows []map[string]any
	if err = json.Unmarshal(data, &rows); err != nil {
		writeJSON(w, 500, map[string]string{"error": "invalid ticker"})
		return
	}
	w.Header().Set("Content-Type", "text/csv; charset=utf-8")
	w.Header().Set("Content-Disposition", "attachment; filename=matchpulse-estimates.csv")
	writer := csv.NewWriter(w)
	defer writer.Flush()
	keys := []string{"person_id", "name", "match_id", "version", "known_at", "model_id", "mode", "status", "currency", "median", "delta", "move_probability", "target"}
	writer.Write(keys)
	for _, row := range rows {
		cells := make([]string, len(keys))
		for i, k := range keys {
			if row[k] != nil {
				cells[i] = fmt.Sprint(row[k])
				if strings.ContainsAny(cells[i][:min(1, len(cells[i]))], "=+@-") {
					cells[i] = "'" + cells[i]
				}
			}
		}
		writer.Write(cells)
	}
}
