package v1

import (
	"log/slog"
	"net/http"
	"net/http/httputil"
	"net/url"
	"strconv"
	"strings"

	"github.com/labstack/echo/v5"

	"github.com/usememos/memos/internal/profile"
	"github.com/usememos/memos/server/auth"
	"github.com/usememos/memos/store"
)

// AgentProxyService proxies requests to the Python agent service.
type AgentProxyService struct {
	profile *profile.Profile
	secret  string
	store   *store.Store
}

// NewAgentProxyService creates an agent proxy service.
func NewAgentProxyService(profile *profile.Profile, secret string, store *store.Store) *AgentProxyService {
	return &AgentProxyService{profile: profile, secret: secret, store: store}
}

// RegisterRoutes registers agent proxy routes on the Echo server.
// If AgentAddr is empty, no routes are registered (agent disabled).
func (s *AgentProxyService) RegisterRoutes(echoServer *echo.Echo) {
	if s.profile.AgentAddr == "" {
		slog.Info("agent proxy disabled (MEMOS_AGENT_ADDR not set)")
		return
	}

	target, err := url.Parse(s.profile.AgentAddr)
	if err != nil {
		slog.Error("invalid agent address", "addr", s.profile.AgentAddr, "error", err)
		return
	}

	proxy := httputil.NewSingleHostReverseProxy(target)

	// Customize the director to rewrite paths: /api/v1/agent/X → /v1/X
	originalDirector := proxy.Director
	proxy.Director = func(req *http.Request) {
		originalDirector(req)
		// Rewrite path: strip /api/v1/agent prefix, add /v1
		// e.g. /api/v1/agent/chat → /v1/chat
		originalPath := req.URL.Path
		stripped := strings.TrimPrefix(originalPath, "/api/v1/agent")
		req.URL.Path = "/v1" + stripped
		req.URL.RawPath = ""
		req.Host = target.Host
	}

	// SSE: flush immediately so the browser receives events as they arrive.
	proxy.FlushInterval = -1

	slog.Info("agent proxy enabled", "target", s.profile.AgentAddr)

	authenticator := auth.NewAuthenticator(s.store, s.secret)

	// Register wildcard route for all agent endpoints.
	echoServer.Any("/api/v1/agent/*", func(c *echo.Context) error {
		// Verify the user's identity from the access token.
		tokenStr := extractAuthToken(c)
		if tokenStr == "" {
			return c.JSON(http.StatusUnauthorized, map[string]string{"detail": "Missing authentication token"})
		}

		claims, err := authenticator.AuthenticateByAccessTokenV2(tokenStr)
		if err != nil {
			return c.JSON(http.StatusUnauthorized, map[string]string{"detail": "Invalid authentication token"})
		}

		req := c.Request()
		// Inject trusted headers for the agent service.
		// The agent service trusts these because requests only arrive via this proxy.
		req.Header.Set("X-User-Id", strconv.Itoa(int(claims.UserID)))
		req.Header.Set("X-User-Name", claims.Username)
		req.Header.Set("X-Auth-Token", tokenStr)

		proxy.ServeHTTP(c.Response(), req)
		return nil
	})
}

// extractAuthToken extracts the user's access token from the request.
// It checks the Authorization header, X-Auth-Token header, and cookies in order.
func extractAuthToken(c *echo.Context) string {
	// Check Authorization: Bearer <token>
	authHeader := c.Request().Header.Get("Authorization")
	if strings.HasPrefix(authHeader, "Bearer ") {
		return strings.TrimPrefix(authHeader, "Bearer ")
	}

	// Check X-Auth-Token header.
	if token := c.Request().Header.Get("X-Auth-Token"); token != "" {
		return token
	}

	// Check cookie.
	cookie, err := c.Request().Cookie("memos.access-token")
	if err == nil && cookie.Value != "" {
		return cookie.Value
	}

	return ""
}
