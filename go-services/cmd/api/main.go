package main

import (
	"context"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"strconv"
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

	if err := godotenv.Load(); err != nil {
		slog.Warn("No .env file found or failed to load, using environment variables")
	}

	pgPool, err := initDB(context.Background())
	if err != nil {
		slog.Error("Database initialization failed", "error", err)
		os.Exit(1)
	}
	defer pgPool.Close()

	jwtSecret := os.Getenv("NEXUS_SECRET_KEY")
	if jwtSecret == "" {
		slog.Error("JWT_SECRET not set")
		os.Exit(1)
	}

	userFeedbackRepo := postgres.NewUserFeedbackRepository(pgPool)
	userGroupRepo := postgres.NewUserGroupRepository(pgPool)

	userFeedbackService := service.NewUserFeedbackServiceImpl(userFeedbackRepo)
	jwtVerifierService := service.NewJwtVerifierService(jwtSecret)

	userFeedbackHandler := deliveryHttp.NewHandler(userFeedbackService)

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

			protectedFeedbacks := feedbacks.Group("", delivery.JWTAuthMiddleware(jwtVerifierService, userGroupRepo))
			{
				protectedFeedbacks.GET("", userFeedbackHandler.ListUserFeedback)
				protectedFeedbacks.GET("/:id", userFeedbackHandler.GetUserFeedback)
				protectedFeedbacks.PATCH("/:id", userFeedbackHandler.UpdateUserFeedback)
			}
		}
	}

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	slog.Info("API Server running", "port", port)
	if err := router.Run(":" + port); err != nil {
		slog.Error("Server failed to run", "error", err)
	}
}

func initDB(ctx context.Context) (*pgxpool.Pool, error) {
	connStr := fmt.Sprintf("postgres://%s:%s@%s:%s/%s?sslmode=disable",
		os.Getenv("NEXUS_DB_USER"),
		os.Getenv("NEXUS_DB_PWD"),
		os.Getenv("NEXUS_DB_HOST"),
		os.Getenv("NEXUS_DB_PORT"),
		os.Getenv("NEXUS_DB_NAME"),
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

func getEnvInt(key string, defaultVal int) int {
	if value, err := strconv.Atoi(os.Getenv(key)); err == nil {
		return value
	}
	return defaultVal
}
