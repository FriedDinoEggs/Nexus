package postgres

import (
	"time"

	"go-services/internal/domain"
)

type PGUserFeedback struct {
	ID        int64     `db:"id" domain:"ID"`
	UserID    *int64    `db:"user_id" domain:"UserID"`
	Email     string    `db:"email" domain:"Email"`
	Category  string    `db:"category" domain:"Category"`
	Title     string    `db:"title" domain:"Title"`
	Message   string    `db:"message" domain:"Message"`
	CreatedAt time.Time `db:"created_at" domain:"CreatedAt"`
	UpdatedAt time.Time `db:"updated_at" domain:"UpdatedAt"`
}

func (puf *PGUserFeedback) ToDomain() domain.UserFeedback {
	return domain.UserFeedback{
		ID:        puf.ID,
		UserID:    puf.UserID,
		Email:     puf.Email,
		Category:  puf.Category,
		Title:     puf.Title,
		Message:   puf.Message,
		CreatedAt: puf.CreatedAt,
		UpdatedAt: puf.UpdatedAt,
	}
}

func fromUserFeedbackDomain(d *domain.UserFeedback) *PGUserFeedback {
	return &PGUserFeedback{
		ID:        d.ID,
		UserID:    d.UserID,
		Email:     d.Email,
		Category:  d.Category,
		Title:     d.Title,
		Message:   d.Message,
		CreatedAt: d.CreatedAt,
		UpdatedAt: d.UpdatedAt,
	}
}
