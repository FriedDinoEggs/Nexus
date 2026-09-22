package main

import (
	"context"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"time"

	"go-services/internal/app/delivery"
	deliveryHttp "go-services/internal/app/delivery/http"
	"go-services/internal/app/repositories/postgres"
	"go-services/internal/app/service"
	"go-services/internal/pkg/response"

	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/joho/godotenv"
)

type TraceHandler struct {
	next slog.Handler
}

func (h *TraceHandler) Handle(ctx context.Context, r slog.Record) error {
	if ctx != nil {
		if traceID, ok := ctx.Value(delivery.TraceIDKey).(string); ok {
			r.AddAttrs(slog.String("trace_id", traceID))
		}
	}
	return h.next.Handle(ctx, r)
}

func NewTraceHandler(next slog.Handler) *TraceHandler {
	return &TraceHandler{next: next}
}

func (h *TraceHandler) Enabled(ctx context.Context, level slog.Level) bool {
	return h.next.Enabled(ctx, level)
}

func (h *TraceHandler) WithAttrs(attrs []slog.Attr) slog.Handler {
	return &TraceHandler{next: h.next.WithAttrs(attrs)}
}

func (h *TraceHandler) WithGroup(name string) slog.Handler {
	return &TraceHandler{next: h.next.WithGroup(name)}
}

func main() {
	jsonHandler := slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelDebug})
	traceHander := NewTraceHandler(jsonHandler)
	logger := slog.New(traceHander)
	slog.SetDefault(logger)

	slog.Info("Starting API Server")

	isProd := false
	var fileConfig map[string]string

	if _, err := os.Stat("/run/secrets/.env.prod"); err == nil {
		isProd = true
		if m, err := godotenv.Read("/run/secrets/.env.prod"); err == nil {
			slog.Info("Production mode: Loaded configurations directly from file into memory")
			fileConfig = m
		} else {
			slog.Error("Failed to read /run/secrets/.env.prod", "error", err)
			os.Exit(1)
		}
	} else if os.Getenv("GIN_MODE") == "release" {
		isProd = true
		if m, err := godotenv.Read(".env.prod"); err == nil {
			slog.Info("Production mode: Loaded .env.prod directly into memory")
			fileConfig = m
		} else {
			slog.Error("Failed to read .env.prod", "error", err)
			os.Exit(1)
		}
	} else {
		if err := godotenv.Load(); err != nil {
			slog.Warn("No .env file found, using system environment variables")
		}
	}

	getConf := func(key string) string {
		if isProd {
			if fileConfig != nil {
				if val, ok := fileConfig[key]; ok && val != "" {
					return val
				}
			}
			slog.Error("Required configuration missing from production file", "key", key)
			os.Exit(1)
		}
		val := os.Getenv(key)
		if val == "" {
			slog.Error("Required configuration missing from environment", "key", key)
			os.Exit(1)
		}
		return val
	}

	pgPool, err := initDB(context.Background(), getConf)
	if err != nil {
		slog.Error("Database initialization failed", "error", err)
		os.Exit(1)
	}
	defer pgPool.Close()

	jwtSecret := getConf("NEXUS_SECRET_KEY")
	if jwtSecret == "" {
		slog.Error("JWT_SECRET not set")
		os.Exit(1)
	}

	userFeedbackRepo := postgres.NewUserFeedbackRepository(pgPool)
	userGroupRepo := postgres.NewUserGroupRepository(pgPool)

	userFeedbackService := service.NewUserFeedbackServiceImpl(userFeedbackRepo)
	feedbackReplyService := service.NewFeedbackReplyServiceImpl(userFeedbackRepo)
	jwtVerifierService := service.NewJwtVerifierService(jwtSecret)

	userFeedbackHandler := deliveryHttp.NewHandler(userFeedbackService, feedbackReplyService)

	router := gin.New()
	router.Use(gin.Recovery())
	router.Use(delivery.TraceMiddleware())
	router.Use(delivery.RequestLoggerMiddleware())

	router.NoRoute(func(c *gin.Context) {
		response.NotFound(c, "Route not found")
	})

	v1 := router.Group("/api/v1")
	{
		v1.GET("/health", func(c *gin.Context) {
			c.JSON(http.StatusOK, gin.H{"status": "ok"})
		})

		feedbacks := v1.Group("/feedbacks")
		{
			feedbacks.POST("", delivery.OptionalJWTAuthMiddleware(jwtVerifierService, userGroupRepo), userFeedbackHandler.CreateUserFeedback)
			feedbacks.GET("/tracking/:token/replies", userFeedbackHandler.GetFeedbackRepliesByToken)

			protectedFeedbacks := feedbacks.Group("", delivery.JWTAuthMiddleware(jwtVerifierService, userGroupRepo))
			{
				protectedFeedbacks.GET("", userFeedbackHandler.ListUserFeedback)
				protectedFeedbacks.GET("/:id", userFeedbackHandler.GetUserFeedback)
				protectedFeedbacks.PATCH("/:id", userFeedbackHandler.UpdateUserFeedback)

				protectedFeedbacks.GET("/replies", userFeedbackHandler.ListFeedbackReplies)
				protectedFeedbacks.POST("/replies", userFeedbackHandler.CreateFeedbackReply)
			}
		}
	}

	port := "8080"
	if isProd {
		if val, ok := fileConfig["PORT"]; ok && val != "" {
			port = val
		}
	} else if val := os.Getenv("PORT"); val != "" {
		port = val
	}

	slog.Info("API Server running", "port", port)
	if err := router.Run(":" + port); err != nil {
		slog.Error("Server failed to run", "error", err)
	}
}

func initDB(ctx context.Context, getConf func(string) string) (*pgxpool.Pool, error) {
	connStr := fmt.Sprintf("postgres://%s:%s@%s:%s/%s?sslmode=disable",
		getConf("NEXUS_DB_USER"),
		getConf("NEXUS_DB_PWD"),
		getConf("NEXUS_DB_HOST"),
		getConf("NEXUS_DB_PORT"),
		getConf("NEXUS_DB_NAME"),
	)

	config, err := pgxpool.ParseConfig(connStr)
	if err != nil {
		return nil, fmt.Errorf("failed to parse DB connection string: %w", err)
	}

	config.MaxConns = 20
	config.MinConns = 5
	config.MaxConnIdleTime = 30 * time.Minute
	config.MaxConnLifetime = 1 * time.Hour
	config.HealthCheckPeriod = 1 * time.Minute

	pgPool, err := pgxpool.NewWithConfig(ctx, config)
	if err != nil {
		return nil, fmt.Errorf("failed to create pgxpool: %w", err)
	}

	pingCtx, cancel := context.WithTimeout(ctx, 3*time.Second)
	defer cancel()

	if err := pgPool.Ping(pingCtx); err != nil {
		return nil, fmt.Errorf("postgres connection ping failed: %w", err)
	}

	slog.Info("PostgreSQL connection pool initialized and pinged successfully")
	return pgPool, nil
}
