package queue

import "context"

type MessageQueue interface {
	Subscribe(ctx context.Context, topic string) (<-chan string, error)
	Close() error
}
