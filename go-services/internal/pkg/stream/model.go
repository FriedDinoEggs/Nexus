package stream

import (
	"encoding/json"
	"strconv"
	"time"

	"go-services/internal/domain"
)

type RedisNotification struct {
	ID        string `json:"id" redis:"id" db:"id"`
	CreatedAt string `json:"createdAt" redis:"created_at" db:"created_at"`
	UpdatedAt string `json:"updatedAt" redis:"updated_at" db:"updated_at"`
	DeletedAt string `json:"-" redis:"-" db:"deleted_at"`
	Title     string `json:"title" redis:"title" db:"title"`
	Body      string `json:"body" redis:"body" db:"body"`
	Payload   string `json:"payload" redis:"payload" db:"payload"`
	Channel   string `json:"channel" redis:"channel" db:"channel"`
	Type      string `json:"type" redis:"type" db:"type"`
	Status    string `json:"status" redis:"status" db:"status"`
	UserID    string `json:"userId" redis:"userId" db:"user_id"`
}

func (rn *RedisNotification) ToDomain() (*domain.Notification, error) {
	id, err := strconv.ParseInt(rn.ID, 10, 64)
	if err != nil {
		return nil, err
	}

	userID, err := strconv.ParseInt(rn.UserID, 10, 64)
	if err != nil {
		return nil, err
	}

	createdAt, err := time.Parse(time.RFC3339, rn.CreatedAt)
	if err != nil {
		return nil, err
	}

	updatedAt, err := time.Parse(time.RFC3339, rn.UpdatedAt)
	if err != nil {
		return nil, err
	}

	return &domain.Notification{
		ID:        id,
		UserID:    userID,
		Title:     rn.Title,
		Body:      rn.Body,
		Payload:   json.RawMessage(rn.Payload),
		Channel:   rn.Channel,
		Type:      rn.Type,
		Status:    rn.Status,
		CreatedAt: createdAt,
		UpdatedAt: updatedAt,
	}, nil
}
