package service

import (
	"context"

	"sse-go-pusher/internal/pkg/queue"
)

type NotificationService struct {
	mq queue.MessageQueue
}

func NewNotificationService(mq queue.MessageQueue) *NotificationService {
	return &NotificationService{mq: mq}
}

func (ns *NotificationService) GetNotificationStream(ctx context.Context, userID string) (<-chan string, error) {
	rawCh, err := ns.mq.Subscribe(ctx, "user_channel_"+userID)
	if err != nil {
		return nil, err
	}

	out := make(chan string, 10)
	go func() {
		defer close(out)

		for {
			select {
			case <-ctx.Done():
				return
			case msg, ok := <-rawCh:
				if !ok {
					return
				}
				select {
				case out <- msg:
				case <-ctx.Done():
					return
				}
			}
		}
	}()

	return out, nil
}
