package delivery

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"strings"
	"time"

	"go-services/internal/domain"
	"go-services/internal/ierrors"
	"go-services/internal/pkg/code"

	"github.com/gin-gonic/gin"
	"github.com/redis/go-redis/v9"
)

type ctxKey struct{}

var TraceIDKey ctxKey

func TraceMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		traceID := c.GetHeader("X-Trace-ID")
		if traceID == "" {
			b := make([]byte, 8)
			_, _ = rand.Read(b)
			traceID = fmt.Sprintf("tr-%d-%s", time.Now().UnixMilli(), hex.EncodeToString(b))
		}

		c.Set("trace_id", traceID)
		c.Header("X-Trace-ID", traceID)

		ctx := c.Request.Context()
		ctx = context.WithValue(ctx, TraceIDKey, traceID)

		c.Request = c.Request.WithContext(ctx)

		c.Next()
	}
}

func RequestLoggerMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		start := time.Now()
		path := c.Request.URL.Path
		rawQuery := c.Request.URL.RawQuery

		c.Next()

		latency := time.Since(start)
		status := c.Writer.Status()
		ctx := c.Request.Context()

		attrs := []any{
			"status", status,
			"method", c.Request.Method,
			"path", path,
			"query", rawQuery,
			"client_ip", c.ClientIP(),
			"latency_ms", latency.Milliseconds(),
			"user_agent", c.Request.UserAgent(),
		}

		if len(c.Errors) > 0 {
			attrs = append(attrs, "errors", c.Errors.String())
		}

		if status >= 500 {
			slog.ErrorContext(ctx, "HTTP Request Completed", attrs...)
		} else if status >= 400 {
			slog.WarnContext(ctx, "HTTP Request Completed", attrs...)
		} else {
			slog.InfoContext(ctx, "HTTP Request Completed", attrs...)
		}
	}
}

func OptionalJWTAuthMiddleware(verifier domain.UserJWTVerifier, userGroupRepo domain.UserGroupRepository) gin.HandlerFunc {
	return func(c *gin.Context) {
		authHeader := c.GetHeader("Authorization")
		if authHeader == "" {
			authHeader = c.GetHeader("Authentication")
		}

		if authHeader == "" {
			c.Next()
			return
		}

		parts := strings.SplitN(authHeader, " ", 2)
		if len(parts) != 2 || parts[0] != "Bearer" {
			c.Next()
			return
		}

		tokenStr := parts[1]
		claims, err := verifier.Verify(tokenStr)
		if err != nil {
			slog.WarnContext(c.Request.Context(), "OptionalJWTAuth: invalid token provided", "error", err, "client_ip", c.ClientIP())
			var ierr *ierrors.APIError
			if errors.Is(err, ierrors.ErrExpiredToken) {
				ierr = ierrors.ErrExpiredToken
			} else if errors.Is(err, ierrors.ErrInvalidToken) {
				ierr = ierrors.ErrInvalidToken
			}
			if ierr == nil {
				ierr = ierrors.NewAPIError(http.StatusUnauthorized, code.Unauthorized, "Invalid token", err, nil)
			}
			c.AbortWithStatusJSON(ierr.HTTPStatus, ierr)
			return
		}

		groupID, err := userGroupRepo.GetGroupIDByUserID(c.Request.Context(), claims.UserID)
		if err != nil {
			groupID = nil
		}

		identity := domain.Identity{
			UserID:  claims.UserID,
			GroupID: groupID,
		}

		c.Set("identity", identity)
		c.Next()
	}
}

func JWTAuthMiddleware(verifier domain.UserJWTVerifier, userGroupRepo domain.UserGroupRepository) gin.HandlerFunc {
	return func(c *gin.Context) {
		authHeader := c.GetHeader("Authorization")
		if authHeader == "" {
			authHeader = c.GetHeader("Authentication")
		}

		if authHeader == "" {
			slog.WarnContext(c.Request.Context(), "JWTAuth: missing authorization header", "client_ip", c.ClientIP(), "path", c.Request.URL.Path)
			ierr := ierrors.NewAPIError(http.StatusUnauthorized, code.Unauthorized, "Missing authorization header", nil, nil)
			c.AbortWithStatusJSON(ierr.HTTPStatus, ierr)
			return
		}

		parts := strings.SplitN(authHeader, " ", 2)
		if len(parts) != 2 || parts[0] != "Bearer" {
			slog.WarnContext(c.Request.Context(), "JWTAuth: invalid authorization header format", "client_ip", c.ClientIP())
			ierr := ierrors.NewAPIError(http.StatusUnauthorized, code.Unauthorized, "Invalid authorization header format", nil, nil)
			c.AbortWithStatusJSON(ierr.HTTPStatus, ierr)
			return
		}

		tokenStr := parts[1]
		claims, err := verifier.Verify(tokenStr)
		if err != nil {
			slog.WarnContext(c.Request.Context(), "JWTAuth: token verification failed", "error", err, "client_ip", c.ClientIP())
			var ierr *ierrors.APIError
			if errors.Is(err, ierrors.ErrExpiredToken) {
				ierr = ierrors.ErrExpiredToken
			} else if errors.Is(err, ierrors.ErrInvalidToken) {
				ierr = ierrors.ErrInvalidToken
			}
			if ierr == nil {
				ierr = ierrors.NewAPIError(http.StatusUnauthorized, code.Unauthorized, "Invalid token", err, nil)
			}
			c.AbortWithStatusJSON(ierr.HTTPStatus, ierr)
			return
		}

		groupID, err := userGroupRepo.GetGroupIDByUserID(c.Request.Context(), claims.UserID)
		if err != nil {
			groupID = nil
		}

		identity := domain.Identity{
			UserID:  claims.UserID,
			GroupID: groupID,
		}

		c.Set("identity", identity)
		c.Next()
	}
}

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
