package queue

import (
	"context"

	"github.com/redis/go-redis/v9"
)

type redisQueue struct {
	client *redis.Client
}

type RedisConfig struct {
	Addr string
	Pwd  string
	DB   int
}

func NewRedisQueue(rdb *redis.Client) *redisQueue {
	return &redisQueue{client: rdb}
}

func (rq *redisQueue) Subscribe(ctx context.Context, topic string) (<-chan string, error) {
	pubsub := rq.client.Subscribe(ctx, topic)
	out := make(chan string, 10)
	ch := pubsub.Channel()

	go func() {
		defer close(out)
		defer pubsub.Close()

		messages, err := rq.client.LRange(ctx, topic, 0, -1).Result()

		if err == nil && len(messages) > 0 {
			rq.client.Del(ctx, topic)
			for _, msgs := range messages {
				select {
				case out <- msgs:
				case <-ctx.Done():
					return
				}
			}
		}

		for {
			select {
			case <-ctx.Done():
				return
			case msg, ok := <-ch:
				if !ok {
					return
				}
				select {
				case out <- msg.Payload:
				case <-ctx.Done():
					return
				}
			}
		}
	}()

	return out, nil
}

func (rq *redisQueue) Close() error { return rq.client.Close() }
