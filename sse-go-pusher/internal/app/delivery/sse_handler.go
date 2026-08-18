package delivery

import (
	"io"
	"log/slog"
	"net/http"
	"strconv"
	"time"

	"sse-go-pusher/internal/app/service"

	"github.com/gin-gonic/gin"
)

type SSEHandler struct {
	service *service.NotificationService
}

func NewSSEHandler(s *service.NotificationService) *SSEHandler {
	return &SSEHandler{service: s}
}

func (sh *SSEHandler) StreamNotifications(c *gin.Context) {
	var req SSENetworkReq

	if err := c.ShouldBindQuery(&req); err != nil {
		slog.Warn("Failed to bind query parameters in SSE stream request", "error", err)
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}
	if err := c.ShouldBindHeader(&req); err != nil {
		slog.Warn("Failed to bind header in SSE stream request", "error", err)
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	userIDStr := c.GetString("userID")
	ticket := c.GetString("ticket")

	userID, err := strconv.ParseInt(userIDStr, 10, 64)
	if err != nil {
		slog.Error("Invalid user ID format in request context", "user_id_raw", userIDStr, "error", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "User ID format error"})
		return
	}

	var lastID int64
	if req.LastID != "" {
		if lID, err := strconv.ParseInt(req.LastID, 10, 64); err == nil {
			lastID = lID
		} else {
			slog.Warn("Invalid Last-Event-ID header value", "last_event_id", req.LastID)
			c.JSON(http.StatusBadRequest, gin.H{"error": "invalid Last-Event-ID"})
			return
		}
	} else {
		lastID = -1
	}

	slog.Info("Establishing SSE stream connection", "user_id", userID, "last_event_id", lastID)

	ch, err := sh.service.GetNotificationStream(c.Request.Context(), userID, lastID)
	if err != nil {
		slog.Error("Failed to initiate notification stream", "user_id", userID, "error", err)
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	heartbeatTimer := time.NewTimer(20 * time.Second)
	defer heartbeatTimer.Stop()

	c.Stream(func(w io.Writer) bool {
		select {
		case <-c.Request.Context().Done():
			slog.Info("SSE client disconnected", "user_id", userID, "ticket", ticket)
			return false
		case <-heartbeatTimer.C:
			slog.Debug("Sending SSE keepalive ping", "user_id", userID, "ticket", ticket)
			c.SSEvent("Ping", "keepalive: "+ticket)
			heartbeatTimer.Reset(20 * time.Second)
			return true
		case msg, ok := <-ch:
			if !ok {
				slog.Info("Notification channel closed for SSE stream", "user_id", userID)
				return false
			}
			slog.Debug("Pushing notification to SSE client", "user_id", userID)
			c.SSEvent("notification", msg)

			if !heartbeatTimer.Stop() {
				select {
				case <-heartbeatTimer.C:
				default:
				}
			}
			heartbeatTimer.Reset(20 * time.Second)
			return true
		}
	})
}

