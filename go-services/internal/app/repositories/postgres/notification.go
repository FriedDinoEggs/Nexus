package postgres

import (
	"context"

	"go-services/internal/domain"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

const getHistoryNotificationQuery = `SELECT * FROM(
											SELECT id, created_at, updated_at, title, body, payload, channel, type, status, user_id
											FROM notification_notification 
											WHERE id > $1 AND user_id = $2 AND deleted_at IS NULL
											ORDER BY id DESC
											LIMIT $3
											) AS subquery
											ORDER BY id ASC`

type NotificationRepository struct {
	db *pgxpool.Pool
}

func NewNotificationRepository(db *pgxpool.Pool) *NotificationRepository {
	return &NotificationRepository{db: db}
}

func (r *NotificationRepository) GetHistory(ctx context.Context, lastID int64, userID int64, limit int) ([]domain.Notification, error) {
	rows, err := r.db.Query(ctx, getHistoryNotificationQuery, lastID, userID, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	models, err := pgx.CollectRows(rows, pgx.RowToStructByName[PGNotificationModel])
	// error
	if err != nil {
		return nil, err
	}

	notis := make([]domain.Notification, len(models))
	for i, model := range models {
		notis[i] = model.ToDomain()
	}
	return notis, nil
}
