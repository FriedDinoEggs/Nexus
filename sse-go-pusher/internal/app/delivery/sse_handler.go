package delivery

import (
	"io"

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
	userID, _ := c.Get("userID")

	ch, _ := sh.service.GetNotificationStream(c.Request.Context(), userID.(string))

	c.Stream(func(w io.Writer) bool {
		select {
		case <-c.Request.Context().Done():
			return false
		case msg, ok := <-ch:
			if !ok {
				return false
			}
			c.SSEvent("notification", msg)
			return true
		}
	})
}
