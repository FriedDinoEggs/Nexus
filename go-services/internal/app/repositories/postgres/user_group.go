package postgres

import (
	"context"

	"go-services/internal/domain"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type userGroupRepository struct {
	db *pgxpool.Pool
}

func NewUserGroupRepository(db *pgxpool.Pool) domain.UserGroupRepository {
	return &userGroupRepository{
		db: db,
	}
}

func (r *userGroupRepository) GetGroupIDByUserID(ctx context.Context, userID int64) ([]int64, error) {
	var groupID []int64
	query := `SELECT group_id FROM core_user_groups WHERE user_id = $1`

	rows, err := r.db.Query(ctx, query, userID)
	if err != nil {
		return nil, err
	}
	groupID, err = pgx.CollectRows(rows, pgx.RowTo[int64])
	if err != nil {
		return nil, err
	}

	return groupID, nil
}
