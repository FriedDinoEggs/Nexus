package delivery

import (
	"log/slog"
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/redis/go-redis/v9"
)

func AuthMiddleware(rdb *redis.Client) gin.HandlerFunc {
	return func(c *gin.Context) {
		ticket := c.Query("ticket")
		if ticket == "" {
			slog.Warn("Authentication failed: missing ticket parameter", "client_ip", c.ClientIP())
			c.JSON(http.StatusBadRequest, gin.H{"error": "Missing ticket"})
			c.Abort()
			return
		}

		redisKey := "sse_ticket:" + ticket
		userID, err := rdb.GetDel(c.Request.Context(), redisKey).Result()

		if err == redis.Nil {
			slog.Warn("Authentication failed: ticket invalid or expired", "ticket", ticket, "client_ip", c.ClientIP())
			c.JSON(http.StatusUnauthorized, gin.H{"error": "Invalid ticket"})
			c.Abort()
			return
		} else if err != nil {
			slog.Error("Redis error during ticket verification", "error", err, "ticket", ticket)
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Internal Server Error"})
			c.Abort()
			return
		}

		slog.Debug("Client authenticated successfully via ticket", "user_id", userID, "ticket", ticket)
		c.Set("userID", userID)
		c.Set("ticket", ticket)
		c.Next()
	}
}
