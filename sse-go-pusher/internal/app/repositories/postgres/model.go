package postgres

import (
	"encoding/json"
	"time"

	"sse-go-pusher/internal/domain"
)

type PGNotificationModel struct {
	ID        int64           `db:"id"`
	CreatedAt time.Time       `db:"created_at"`
	UpdatedAt time.Time       `db:"updated_at"`
	Title     string          `db:"title"`
	Body      string          `db:"body"`
	Payload   json.RawMessage `db:"payload"`
	Channel   string          `db:"channel"`
	Type      string          `db:"type"`
	Status    string          `db:"status"`
	UserID    int64           `db:"user_id"`
}

func (pn *PGNotificationModel) ToDomain() domain.Notification {
	return domain.Notification{
		ID:        pn.ID,
		UserID:    pn.UserID,
		Title:     pn.Title,
		Body:      pn.Body,
		Payload:   []byte(pn.Payload),
		Channel:   pn.Channel,
		Type:      pn.Type,
		Status:    pn.Status,
		CreatedAt: pn.CreatedAt,
		UpdatedAt: pn.UpdatedAt,
	}
}
