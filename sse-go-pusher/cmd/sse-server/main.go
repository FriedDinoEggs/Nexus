package main

import (
	"context"
	"fmt"
	"log/slog"
	"os"
	"strconv"
	"time"

	"sse-go-pusher/internal/app/delivery"
	"sse-go-pusher/internal/app/repositories/postgres"
	"sse-go-pusher/internal/app/service"
	"sse-go-pusher/internal/pkg/stream"

	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/joho/godotenv"
	"github.com/redis/go-redis/v9"
)

var (
	rdb    *redis.Client
	pgPool *pgxpool.Pool
)

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
		Level: slog.LevelDebug,
	}))
	slog.SetDefault(logger)

	slog.Info("Starting SSE Push Server...")

	if err := InitDB(context.Background()); err != nil {
		slog.Error("Database initialization failed", "error", err)
		os.Exit(1)
	}
	defer func() {
		if rdb != nil {
			rdb.Close()
		}
		if pgPool != nil {
			pgPool.Close()
		}
		slog.Info("Database and Redis connections closed")
	}()

	var streamReader stream.StreamReader = stream.NewRedisStream(rdb)
	repo := postgres.NewNotificationRepository(pgPool)
	notiService := service.NewNotificationService(repo, streamReader)
	sseHandler := delivery.NewSSEHandler(notiService)

	router := gin.New()
	router.Use(gin.Recovery())

	v1 := router.Group("api/v1")
	{
		notification := v1.Group("/notification")
		{

			notification.GET("/stream/health/", func(c *gin.Context) { c.String(200, "OK") })
			notificationGroup := notification.Group("/stream", delivery.AuthMiddleware(rdb))
			notificationGroup.GET("/", sseHandler.StreamNotifications)
		}
	}
	// v1.Use(delivery.AuthMiddleware(rdb))
	// {
	// 	v1.GET("notification/stream/", sseHandler.StreamNotifications)
	//
	//
	// 	v1.GET("health/", func(c *gin.Context) { c.String(200, "OK") })
	// }

	slog.Info("HTTP server running")
	if err := router.Run(); err != nil {
		slog.Error("Server failed to run", "error", err)
	}
}

func InitDB(ctx context.Context) error {
	if err := godotenv.Load(); err != nil {
		slog.Warn("No .env file found or failed to load, falling back to system environment variables", "error", err)
	}

	cfg := struct {
		Addr string
		Pwd  string
		DB   int
	}{
		Addr: fmt.Sprintf("%s:%s", os.Getenv("REDIS_HOST"), os.Getenv("REDIS_PORT")),
		Pwd:  os.Getenv("REDIS_PASSWORD"),
		DB:   getEnvInt("REDIS_DB", 0),
	}

	rdb = redis.NewClient(&redis.Options{
		Addr:         cfg.Addr,
		Password:     cfg.Pwd,
		DB:           cfg.DB,
		PoolSize:     100,
		MinIdleConns: 10,
	})
	slog.Info("Redis client configured", "addr", cfg.Addr, "db", cfg.DB)

	connStr := fmt.Sprintf("postgres://%s:%s@%s:%s/%s?sslmode=disable",
		os.Getenv("NEXUS_DB_USER"), os.Getenv("NEXUS_DB_PWD"),
		os.Getenv("NEXUS_DB_HOST"), os.Getenv("NEXUS_DB_PORT"),
		os.Getenv("NEXUS_DB_NAME"),
	)
	config, err := pgxpool.ParseConfig(connStr)
	if err != nil {
		return fmt.Errorf("failed to parse connection string: %w", err)
	}
	config.MaxConns = 20
	config.MinConns = 5
	config.MaxConnIdleTime = 30 * time.Minute
	config.MaxConnLifetime = 1 * time.Hour
	config.HealthCheckPeriod = 1 * time.Minute

	pgPool, err = pgxpool.NewWithConfig(context.Background(), config)
	if err != nil {
		return fmt.Errorf("failed to create pgxpool: %w", err)
	}

	pingCtx, cancel := context.WithTimeout(ctx, 3*time.Second)
	defer cancel()

	if err := pgPool.Ping(pingCtx); err != nil {
		return fmt.Errorf("postgres connection ping failed: %w", err)
	}

	slog.Info("PostgreSQL connection pool initialized and pinged successfully")
	return nil
}

func getEnvInt(key string, defaultVal int) int {
	if value, err := strconv.Atoi(os.Getenv(key)); err == nil {
		return value
	}
	return defaultVal
}
