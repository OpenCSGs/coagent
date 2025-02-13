package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"log/slog"
	"net/http"
	"strings"
)

type AddrType struct {
	Name string `json:"name"`
	Id   string `json:"id"`
}

type Content struct {
	Addr AddrType `json:"addr"`
}

type HeaderType struct {
	Type string `json:"type"`
}

type RawMessage struct {
	Header  HeaderType     `json:"header"`
	Content string         `json:"content"`
	Reply   map[string]any `json:"reply"`
}

type Channel struct {
	server string
	auth   string
	client *http.Client
}

// NewChannel creates a new Channel instance
func NewChannel(server, auth string) *Channel {
	return &Channel{
		server: server,
		auth:   auth,
		client: &http.Client{},
	}
}

// publish method to publish messages
func (c *Channel) Publish(addr map[string]any, msg map[string]any) error {
	data := map[string]any{
		"addr": addr,
		"msg":  msg,
	}

	jsonData, err := json.Marshal(data)
	if err != nil {
		return fmt.Errorf("[channel.publish] failed to marshal data: %w", err)
	}
	buf := bytes.NewBuffer(jsonData)

	url := fmt.Sprintf("%s/runtime/channel/publish", c.server)
	req, err := http.NewRequest("POST", url, buf)
	if err != nil {
		return fmt.Errorf("[Channel.Publish] Error creating request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	if c.auth != "" {
		req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", c.auth))
	}

	resp, err := c.client.Do(req)
	if err != nil {
		return fmt.Errorf("[channel.Publish] failed to post data: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusNoContent {
		return fmt.Errorf("[channel.Publish] failed to publish: %s", resp.Status)
	}
	return nil
}

// subscribe method to subscribe to events
func (c *Channel) Subscribe(path string, data map[string]any, handler func(string)) {
	jsonData, err := json.Marshal(data)
	if err != nil {
		slog.Error("[Channel.Subscribe] failed to marshal data.", slog.Any("err", err))
		return
	}
	buf := bytes.NewBuffer(jsonData)
	slog.Info("[Channel.Subscribe] sse body data.", slog.Any("buf", buf.String()))

	url := fmt.Sprintf("%s%s", c.server, path)

	req, err := http.NewRequest("POST", url, buf)
	if err != nil {
		slog.Error("[Channel.Subscribe] Error creating request.", slog.Any("err", err))
		return
	}
	req.Header.Set("Content-Type", "application/json")
	if c.auth != "" {
		req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", c.auth))
	}

	resp, err := c.client.Do(req)
	if err != nil {
		slog.Error("[Channel.Subscribe] Error sending request.", slog.Any("err", err))
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		slog.Error("[Channel.Subscribe] Unexpected status code.", slog.Any("resp.StatusCode", resp.StatusCode))
		return
	}

	// handle SSE Events
	scanner := bufio.NewScanner(resp.Body)
	for scanner.Scan() {
		line := scanner.Text()
		if len(line) > 0 && line[0] != ':' { // Ignore comments
			slog.Info("[Channel.Subscribe] SSE Received.", slog.Any("line", line), slog.Any("path", path))
			handler(line)
		}
	}

	err = scanner.Err()
	if err != nil {
		slog.Error("[Channel.Subscribe] Error reading SSE data.", slog.Any("err", err))
	}
}

// Runtime struct for managing agents
type Runtime struct {
	channel   *Channel
	factories map[string]func() Agent
}

// NewRuntime creates a new Runtime instance
func NewRuntime(server, auth string) *Runtime {
	return &Runtime{
		channel:   NewChannel(server, auth),
		factories: make(map[string]func() Agent),
	}
}

func (r *Runtime) Register(name string, constructor func() Agent, description string) error {
	_, exists := r.factories[name]
	if exists {
		return fmt.Errorf("Agent %s already registered", name)
	}
	r.factories[name] = constructor

	data := map[string]any{
		"name":        name,
		"description": description,
	}
	slog.Info("[Runtime.Register] Register agent success.", slog.Any("name", name))
	go r.channel.Subscribe("/runtime/register", data, r.Handle)
	return nil
}

func (r *Runtime) Handle(data string) {
	line := strings.TrimSpace(strings.TrimPrefix(data, "data:"))
	msg := RawMessage{}
	err := json.Unmarshal([]byte(line), &msg)
	if err != nil {
		slog.Error("[Runtime.Handle] Error unmarshalling message.", slog.Any("err", err), slog.Any("line", line))
		return
	}
	slog.Info("[Runtime.Handle] received message.", slog.Any("msg.Header", msg.Header), slog.Any("msg.Content", msg.Content))
	headerType := msg.Header.Type
	switch headerType {
	case "AgentCreated":
		r.CreateAgent(msg)
	case "AgentDeleted":
		r.DeleteAgent(msg)
	}
}

func (r *Runtime) CreateAgent(msg RawMessage) {
	content := Content{}
	err := json.Unmarshal([]byte(msg.Content), &content)
	if err != nil {
		slog.Error("[Runtime.CreateAgent] Error unmarshalling content.", slog.Any("err", err), slog.Any("msg.Content", msg.Content))
		return
	}
	// addr := data["content"].(map[string]any)["addr"]
	// agentName := addr.(map[string]any)["name"].(string)
	addr := content.Addr
	agentName := content.Addr.Name
	constructor := r.factories[agentName]
	slog.Info("[Runtime.CreateAgent] Creating agent.", slog.Any("agentName", agentName))
	agent := constructor()
	go r.channel.Subscribe("/runtime/channel/subscribe", map[string]any{"addr": addr}, agent.Receive)
}

func (r *Runtime) DeleteAgent(msg RawMessage) {
	// Logic to delete an agent can go here
}

type Agent interface {
	Receive(data string)
	Handle(msg RawMessage) map[string]any
}

var _ Agent = (*Server)(nil)

type Server struct {
	channel *Channel
	addr    map[string]any
}

func NewServer(channel *Channel, addr map[string]any) *Server {
	return &Server{channel: channel, addr: addr}
}

func (a *Server) Receive(data string) {
	slog.Info("[Server.Receive] received a message.", slog.Any("data", data))
	line := strings.TrimSpace(strings.TrimPrefix(data, "data:"))
	msg := RawMessage{}
	err := json.Unmarshal([]byte(line), &msg)
	if err != nil {
		slog.Error("[Server.Receive] Error unmarshalling message.", slog.Any("err", err), slog.Any("line", line))
		return
	}
	result := a.Handle(msg)
	slog.Info("[Server.Receive] handle result.", slog.Any("result", result))

	slog.Info("[Server.Receive] reply.", slog.Any("msg.Reply", msg.Reply))
	replyAddr, ok := msg.Reply["address"].(map[string]any)
	if !ok || len(replyAddr) == 0 {
		return
	}

	err = a.channel.Publish(replyAddr, result)
	if err != nil {
		slog.Error("[Server.Receive] Error publishing reply.", slog.Any("err", err), slog.Any("msg.Reply", msg.Reply))
	}
}

func (s *Server) Handle(msg RawMessage) map[string]any {
	return map[string]any{
		"header": map[string]any{"type": "Pong"},
	}
}

func main() {
	server := flag.String("server", "http://127.0.0.1:8000", "")
	auth := flag.String("auth", "", "")
	flag.Parse()

	runtime := NewRuntime(*server, *auth)
	err := runtime.Register("server", func() Agent { return NewServer(runtime.channel, nil) }, "An example CoS Go agent.")
	if err != nil {
		slog.Error("Failed to register server", slog.Any("err", err))
		return
	}

	idleLoop()
}

func idleLoop() {
	select {}
}
