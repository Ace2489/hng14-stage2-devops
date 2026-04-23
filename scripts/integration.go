package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"os/exec"
	"time"
)

func logf(s string, args ...any) {
	fmt.Fprintf(os.Stderr, s+"\n", args...)
}

func sh(args ...string) {
	logf("→ %s", args)
	c := exec.Command(args[0], args[1:]...)
	c.Stdout, c.Stderr = os.Stdout, os.Stderr
	if err := c.Run(); err != nil {
		logf("✗ command failed: %v", err)
		os.Exit(1)
	}
}

func retry(name string, n int, f func() bool) {
	for i := 1; i <= n; i++ {
		if f() {
			logf("✓ %s (attempt %d)", name, i)
			return
		}
		logf("… %s retry %d/%d", name, i, n)
		time.Sleep(2 * time.Second)
	}
	logf("✗ %s failed after %d attempts", name, n)
	os.Exit(1)
}

func main() {
	defer sh("docker", "compose", "down", "-v", "--remove-orphans")

	port := os.Getenv("FRONTEND_PORT")
	if port == "" {
		panic("✗ No frontend port configured")
	}
	base := "http://localhost:" + port

	logf("starting stack")
	sh("docker", "compose", "--env-file", ".env", "up", "-d", "--no-build")

	retry("health check: "+base, 40, func() bool {
		r, e := http.Get(base + "/health")
		return e == nil && r.StatusCode == 200
	})

	var jobID string
	retry("submit job", 5, func() bool {
		r, e := http.Post(base+"/submit", "application/json", nil)
		if e != nil || r.StatusCode != 201 {
			return false
		}
		defer r.Body.Close()
		return json.NewDecoder(r.Body).Decode(&struct {
			JobID *string `json:"job_id"`
		}{&jobID}) == nil && jobID != ""
	})

	logf("job submitted: %s", jobID)

	retry("job completion", 30, func() bool {
		r, e := http.Get(base + "/status/" + jobID)
		if e != nil || r.StatusCode != 200 {
			return false
		}
		defer r.Body.Close()
		var s struct{ Status string }
		ok := json.NewDecoder(r.Body).Decode(&s) == nil && s.Status == "completed"
		if !ok {
			logf("status=%s", s.Status)
		}
		return ok
	})

	logf("✓ integration test passed")
}
