package server

import (
	"bufio"
	"context"
	"encoding/csv"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

type stub struct{}

func (stub) Call(ctx context.Context, op string, args any) (json.RawMessage, error) {
	return json.RawMessage(`{"seq":0}`), nil
}

func TestMutationContracts(t *testing.T) {
	handler := (&Server{Engine: stub{}, Assets: t.TempDir()}).Handler()
	for _, tc := range []struct {
		body, origin, ctype string
		want                int
	}{
		{`{}`, "http://evil.invalid", "application/json", 403},
		{`{}`, "", "text/plain", 415},
		{`null`, "", "application/json", 400},
		{`{} {}`, "", "application/json", 400},
		{`{} garbage`, "", "application/json", 400},
		{strings.Repeat("x", 1024*1024+1), "", "application/json", 400},
		{`{}`, "", "application/json", 200},
	} {
		r := httptest.NewRequest("POST", "http://localhost/api/replay/step", strings.NewReader(tc.body))
		r.Header.Set("Origin", tc.origin)
		r.Header.Set("Content-Type", tc.ctype)
		w := httptest.NewRecorder()
		handler.ServeHTTP(w, r)
		if w.Code != tc.want {
			t.Fatalf("got %d want %d: %s", w.Code, tc.want, w.Body.String())
		}
	}
}

func TestActualWorkerReplayCSVAndReconnect(t *testing.T) {
	old, err := os.Getwd()
	if err != nil {
		t.Fatal(err)
	}
	root := filepath.Join(old, "..", "..")
	if err = os.Chdir(root); err != nil {
		t.Fatal(err)
	}
	defer os.Chdir(old)
	worker := NewWorker("python3", filepath.Join(t.TempDir(), "state.db"))
	defer worker.Close()
	server := httptest.NewServer((&Server{Engine: worker, Assets: t.TempDir()}).Handler())
	defer server.Close()
	resp, err := http.Post(server.URL+"/api/replay/step", "application/json", strings.NewReader(`{"finish":true}`))
	if err != nil {
		t.Fatal(err)
	}
	raw, _ := io.ReadAll(resp.Body)
	resp.Body.Close()
	if resp.StatusCode != 200 || !strings.Contains(string(raw), `"finished"`) {
		t.Fatalf("replay: %d %s", resp.StatusCode, raw)
	}
	resp, err = http.Post(server.URL+"/api/replay/step", "application/json", strings.NewReader(`{}`))
	if err != nil {
		t.Fatal(err)
	}
	raw, _ = io.ReadAll(resp.Body)
	resp.Body.Close()
	if !strings.Contains(string(raw), `"guaranteed":19000000`) {
		t.Fatal("missing separate later sale")
	}
	resp, err = http.Get(server.URL + "/api/export.csv")
	if err != nil {
		t.Fatal(err)
	}
	records, err := csv.NewReader(resp.Body).ReadAll()
	resp.Body.Close()
	if err != nil || len(records) != 24 {
		t.Fatalf("CSV rows: %d %v", len(records), err)
	}
	for _, record := range records[1:] {
		if record[6] != "synthetic" {
			t.Fatal("CSV lost mode")
		}
	}
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	req, _ := http.NewRequestWithContext(ctx, "GET", server.URL+"/api/events", nil)
	req.Header.Set("Last-Event-ID", "40")
	resp, err = http.DefaultClient.Do(req)
	if err != nil {
		cancel()
		t.Fatal(err)
	}
	scan := bufio.NewScanner(resp.Body)
	found := false
	for scan.Scan() {
		if strings.HasPrefix(scan.Text(), "id: 41") {
			found = true
			break
		}
	}
	resp.Body.Close()
	cancel()
	if !found {
		t.Fatal("durable resume omitted sequence 41")
	}
	worker.stop()
	ctx, cancel = context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	data, err := worker.Call(ctx, "state", map[string]any{})
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(data), `"guaranteed":19000000`) {
		t.Fatal("restart lost committed state")
	}
}

func TestTokenProtectsReadAndWrites(t *testing.T) {
	h := (&Server{Engine: stub{}, Assets: t.TempDir(), Token: "test-token"}).Handler()
	for _, path := range []string{"/api/state", "/api/events"} {
		r := httptest.NewRequest("GET", path, nil)
		w := httptest.NewRecorder()
		h.ServeHTTP(w, r)
		if w.Code != 401 {
			t.Fatal("unprotected read")
		}
	}
	r := httptest.NewRequest("GET", "/api/state", nil)
	r.Header.Set("Authorization", "Bearer test-token")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, r)
	if w.Code != 200 {
		t.Fatal("valid token rejected")
	}
}
