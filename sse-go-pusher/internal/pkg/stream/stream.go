package stream

import (
	"context"

	"sse-go-pusher/internal/domain"
)

type StreamReader interface {
	Read(ctx context.Context, topic string, handler Handler) (<-chan MessageStream, error)

	Close() error
}

type MessageStream struct {
	Noti *domain.Notification
	Err  error
}

type Handler func(ctx context.Context, noti *domain.Notification) error
