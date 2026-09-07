package domain

import "context"

type UserGroupRepository interface {
	GetGroupIDByUserID(ctx context.Context, userID int64) ([]int64, error)
}
