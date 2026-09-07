package domain

import (
	"context"
	"time"
)

type UserFeedback struct {
	ID       int64
	UserID   *int64
	Email    string
	Category string
	Title    string
	Message  string

	CreatedAt time.Time
	UpdatedAt time.Time
}

type UserFeedbackRepository interface {
	FindAll(ctx context.Context, input ListFeedbackInput, filter FeedbackFilter) ([]UserFeedback, bool, error)
	FindByID(ctx context.Context, ID int64, filter FeedbackFilter) (UserFeedback, error)
	Create(ctx context.Context, input CreateFeedbackInput) (UserFeedback, error)
	Update(ctx context.Context, ID int64, input UpdateFeedbackInput, filter FeedbackFilter) (UserFeedback, error)
}

type UpdateFeedbackInput struct {
	Email    *string
	Category *string
	Title    *string
	Message  *string
}

type CreateFeedbackInput struct {
	UserID   *int64
	Email    string
	Category string
	Title    string
	Message  string
}

type ListFeedbackInput struct {
	Page  int
	Limit int
}

type FeedbackFilter struct {
	UserID   *int64
	Category *string
	Status   *string
}
