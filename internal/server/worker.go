package server

import (
	"bufio"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"sync"
)

var ErrBusy = errors.New("engine request queue is full")

type Reply struct {
	OK    bool            `json:"ok"`
	Data  json.RawMessage `json:"data"`
	Error string          `json:"error"`
	Code  string          `json:"code"`
}

type Worker struct {
	python   string
	db       string
	slots    chan struct{}
	gate     chan struct{}
	cmd      *exec.Cmd
	stdin    io.WriteCloser
	replies  chan Reply
	failures chan error
	mu       sync.Mutex
	closed   bool
}

func NewWorker(python, db string) *Worker {
	return &Worker{python: python, db: db, slots: make(chan struct{}, 64), gate: make(chan struct{}, 1)}
}

func (w *Worker) start() error {
	w.mu.Lock()
	defer w.mu.Unlock()
	if w.closed {
		return errors.New("worker closed")
	}
	if w.cmd != nil {
		return nil
	}
	cmd := exec.Command(w.python, "-m", "matchpulse.rpc", "--db", w.db)
	stdin, err := cmd.StdinPipe()
	if err != nil {
		return err
	}
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		stdin.Close()
		return err
	}
	cmd.Stderr = os.Stderr
	if err = cmd.Start(); err != nil {
		stdin.Close()
		return err
	}
	w.cmd = cmd
	w.stdin = stdin
	replies := make(chan Reply, 1)
	failures := make(chan error, 1)
	w.replies = replies
	w.failures = failures
	go func() {
		scan := bufio.NewScanner(stdout)
		scan.Buffer(make([]byte, 65536), 32*1024*1024)
		for scan.Scan() {
			var reply Reply
			if err := json.Unmarshal(scan.Bytes(), &reply); err != nil {
				failures <- err
				return
			}
			replies <- reply
		}
		err := scan.Err()
		if err == nil {
			err = io.EOF
		}
		failures <- err
	}()
	return nil
}

func (w *Worker) stop() {
	w.mu.Lock()
	defer w.mu.Unlock()
	if w.cmd != nil {
		w.stdin.Close()
		w.cmd.Process.Kill()
		w.cmd.Wait()
		w.cmd = nil
	}
}

func (w *Worker) Close() {
	w.mu.Lock()
	w.closed = true
	w.mu.Unlock()
	w.stop()
}

func (w *Worker) Call(ctx context.Context, op string, args any) (json.RawMessage, error) {
	select {
	case w.slots <- struct{}{}:
	default:
		return nil, ErrBusy
	}
	defer func() { <-w.slots }()
	select {
	case w.gate <- struct{}{}:
	case <-ctx.Done():
		return nil, ctx.Err()
	}
	defer func() { <-w.gate }()
	if err := w.start(); err != nil {
		return nil, err
	}
	frame, err := json.Marshal(map[string]any{"op": op, "args": args})
	if err != nil {
		return nil, err
	}
	if len(frame) > 1024*1024 {
		return nil, errors.New("request too large")
	}
	if _, err = w.stdin.Write(append(frame, '\n')); err != nil {
		w.stop()
		return nil, err
	}
	select {
	case reply := <-w.replies:
		if !reply.OK {
			return nil, fmt.Errorf("%s: %s", reply.Code, reply.Error)
		}
		return reply.Data, nil
	case err := <-w.failures:
		w.stop()
		return nil, err
	case <-ctx.Done():
		w.stop()
		return nil, ctx.Err()
	}
}
