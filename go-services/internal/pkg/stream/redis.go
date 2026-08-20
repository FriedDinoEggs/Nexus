package stream

import (
	"context"
	"errors"
	"log/slog"
	"time"

	"github.com/redis/go-redis/v9"
)

type redisStream struct {
	client *redis.Client
}

func NewRedisStream(client *redis.Client) *redisStream {
	return &redisStream{client: client}
}

func (rs *redisStream) Read(ctx context.Context, topic string, handler Handler) (<-chan MessageStream, error) {
	out := make(chan MessageStream, 10)

	go func() {
		defer func() {
			close(out)
			slog.Debug("Redis stream reader goroutine closed", "topic", topic)
		}()

		readPosition := "$"
		for {
			streams, err := rs.client.XRead(ctx, &redis.XReadArgs{
				Streams: []string{topic, readPosition},
				Count:   10,
				Block:   2 * time.Second,
			}).Result()
			if err != nil {
				if errors.Is(err, context.Canceled) || errors.Is(ctx.Err(), context.Canceled) {
					slog.Debug("Redis stream reading canceled by context", "topic", topic)
					return
				}
				if errors.Is(err, redis.Nil) {
					continue
				}
				slog.Error("Unexpected error reading from Redis stream", "topic", topic, "error", err)
				time.Sleep(1 * time.Second)
				continue
			}

			for _, stream := range streams {
				for _, msg := range stream.Messages {
					readPosition = msg.ID

					model := RedisNotification{
						ID:        getString(msg.Values, "id"),
						UserID:    getString(msg.Values, "user_id"),
						Title:     getString(msg.Values, "title"),
						Body:      getString(msg.Values, "body"),
						Payload:   getString(msg.Values, "payload"),
						Channel:   getString(msg.Values, "channel"),
						Type:      getString(msg.Values, "type"),
						Status:    getString(msg.Values, "status"),
						CreatedAt: getString(msg.Values, "created_at"),
						UpdatedAt: getString(msg.Values, "updated_at"),
					}

					noti, err := model.ToDomain()
					if err != nil {
						slog.Warn("Failed to map redis message to domain notification", "topic", topic, "msg_id", msg.ID, "error", err)
						continue
					}

					select {
					case <-ctx.Done():
						slog.Debug("Context canceled during message dispatch in redisStream", "topic", topic)
						return
					case out <- MessageStream{Noti: noti}:
					}
				}
			}
		}
	}()

	return out, nil
}

func (rs *redisStream) Close() error {
	return nil
}

func getString(source map[string]any, key string) string {
	if v, ok := source[key].(string); ok {
		return v
	}
	return ""
}

