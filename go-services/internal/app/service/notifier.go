package service

import (
	"context"
	"encoding/json"
	"log/slog"
	"strconv"

	"go-services/internal/domain"
	"go-services/internal/pkg/stream"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/redis/go-redis/v9"
)

type NotificationService struct {
	repo   domain.NotificationRepository
	stream stream.StreamReader
}

type NotificationHandler struct {
	db  *pgxpool.Pool
	rdb *redis.Client
}

func NewNotificationService(repo domain.NotificationRepository, stream stream.StreamReader) *NotificationService {
	return &NotificationService{repo: repo, stream: stream}
}

func (ns *NotificationService) GetNotificationStream(ctx context.Context, userID, lastNotificationID int64) (<-chan string, error) {
	var processingMessage stream.Handler
	streamTopic := "user_notification_stream:" + strconv.FormatInt(userID, 10)
	out := make(chan string, 10)

	slog.Info("Subscribing to notification stream", "user_id", userID, "topic", streamTopic)

	messageStream, err := ns.stream.Read(ctx, streamTopic, processingMessage)
	if err != nil {
		slog.Error("Failed to read from notification stream", "user_id", userID, "topic", streamTopic, "error", err)
		return nil, err
	}

	go func() {
		defer func() {
			if r := recover(); r != nil {
				slog.Error("Recovered from panic in notification stream goroutine", "panic", r, "user_id", userID)
			}
			close(out)
			slog.Info("Notification stream goroutine exiting", "user_id", userID)
		}()

		err = ns.StreamHistory(ctx, userID, &lastNotificationID, out)
		if err != nil {
			slog.Error("Failed to stream history notifications", "user_id", userID, "error", err)
			return
		}

		for {
			select {
			case <-ctx.Done():
				slog.Debug("Context canceled in notification stream loop", "user_id", userID)
				return
			case msg, ok := <-messageStream:
				if !ok {
					slog.Debug("Incoming messageStream channel closed", "user_id", userID)
					return
				} else if msg.Err != nil {
					slog.Error("Received error from message stream", "user_id", userID, "error", msg.Err)
					continue
				} else {
					if lastNotificationID >= msg.Noti.ID {
						continue
					}
					jn, err := json.Marshal(msg.Noti)
					if err != nil {
						slog.Error("Failed to marshal notification message", "user_id", userID, "notification_id", msg.Noti.ID, "error", err)
						continue
					}

					select {
					case <-ctx.Done():
						return
					case out <- string(jn):
						slog.Debug("Pushed realtime notification to user stream", "user_id", userID, "notification_id", msg.Noti.ID)
					}
				}
			}
		}
	}()

	return out, nil
}

func (ns *NotificationService) StreamHistory(ctx context.Context, userID int64, lastID *int64, out chan<- string) error {
	slog.Info("Fetching history notifications", "user_id", userID, "last_id", *lastID)
	notis, err := ns.repo.GetHistory(ctx, *lastID, userID, 20)
	if err != nil {
		slog.Error("Repository GetHistory failed", "user_id", userID, "last_id", *lastID, "error", err)
		return err
	}

	for _, noti := range notis {
		*lastID = noti.ID

		jn, err := json.Marshal(noti)
		if err != nil {
			slog.Warn("Failed to marshal history notification", "user_id", userID, "notification_id", noti.ID, "error", err)
			continue
		}
		select {
		case <-ctx.Done():
			slog.Debug("Context canceled during StreamHistory", "user_id", userID)
			return nil
		case out <- string(jn):
			slog.Debug("Pushed history notification to user stream", "user_id", userID, "notification_id", noti.ID)
		}
	}
	return nil
}
