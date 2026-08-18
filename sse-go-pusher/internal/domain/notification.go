package domain

import (
	"context"
	"database/sql"
	"encoding/json"
	"time"
)

type Notification struct {
	ID        int64
	CreatedAt time.Time
	UpdatedAt time.Time
	DeletedAt sql.NullTime
	Title     string
	Body      string
	Payload   json.RawMessage
	Channel   string
	Type      string
	Status    string
	UserID    int64
}

type NotificationRepository interface {
	GetHistory(ctx context.Context, lastID int64, userID int64, limit int) ([]Notification, error)
}
