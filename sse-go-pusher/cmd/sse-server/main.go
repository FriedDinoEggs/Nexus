package main

import (
	"fmt"
	"log"
	"net/http"
	"os"
	"strconv"

	"sse-go-pusher/internal/app/delivery"
	"sse-go-pusher/internal/app/service"
	"sse-go-pusher/internal/pkg/queue"

	"github.com/gin-gonic/gin"
	"github.com/joho/godotenv"
	"github.com/redis/go-redis/v9"
)

type Ticket struct {
	Ticket string `form:"ticket" binding:"required,uuid"`
}

var rdb *redis.Client

func main() {
	if err := godotenv.Load(); err != nil {
		log.Fatal("error loading .env file")
	}

	cfg := queue.RedisConfig{
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
	defer rdb.Close()

	var mq queue.MessageQueue = queue.NewRedisQueue(rdb)

	notiServeice := service.NewNotificationService(mq)
	sseHandler := delivery.NewSSEHandler(notiServeice)

	router := gin.Default()

	v1 := router.Group("api/v1")
	v1.Use(TicketAuthMiddleware(rdb))
	{
		v1.GET("notification/stream/", sseHandler.StreamNotifications)
	}

	router.Run()
}

func getEnvInt(key string, defaultVal int) int {
	if value, err := strconv.Atoi(os.Getenv(key)); err == nil {
		return value
	}
	return defaultVal
}

func TicketAuthMiddleware(rdb *redis.Client) gin.HandlerFunc {
	return func(c *gin.Context) {
		ticket := c.Query("ticket")

		if ticket == "" {
			c.JSON(http.StatusUnauthorized, gin.H{"error": "Invalid ticket"})
			c.Abort()
			return
		}

		redisKey := "sse_ticket:" + ticket
		userID, err := rdb.GetDel(c.Request.Context(), redisKey).Result()
		if err == redis.Nil {
			c.JSON(http.StatusUnauthorized, gin.H{"error": "Invalid ticket"})
			c.Abort()
			return
		} else if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Interanl Server Error"})
			c.Abort()
			return
		}

		c.Set("userID", userID)
		c.Next()
	}
}
