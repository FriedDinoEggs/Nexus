package domain

import (
	"context"
	"time"

	"github.com/google/uuid"
)

type UserFeedback struct {
	ID            int64
	UserID        *int64
	TrackingToken uuid.UUID
	Email         string
	Category      string
	Title         string
	Message       string

	CreatedAt time.Time
	UpdatedAt time.Time
}

type UserFeedbackByID interface {
	FindAll(ctx context.Context, input ListFeedbackInput, filter FeedbackFilter) ([]UserFeedback, bool, error)
	FindByID(ctx context.Context, ID int64, filter FeedbackFilter) (UserFeedback, error)
	Create(ctx context.Context, input CreateFeedbackInput) (UserFeedback, error)
	Update(ctx context.Context, ID int64, input UpdateFeedbackInput, filter FeedbackFilter) (UserFeedback, error)
}

type UserFeedbackByTrackingToken interface {
	FindByTrackingToken(ctx context.Context, token uuid.UUID) (UserFeedback, error)
}

type FeedbackReplyRepo interface {
	FindAll(ctx context.Context, input ListFeedbackReplyInput) ([]FeedbackReply, bool, error)
	FindByToken(ctx context.Context, token uuid.UUID) ([]FeedbackReply, error)
	Create(ctx context.Context, input CreateFeedbackReplyInput) (FeedbackReply, error)
}

type UserFeedbackRepository interface {
	UserFeedbackByID
	UserFeedbackByTrackingToken
	Replies() FeedbackReplyRepo
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

type FeedbackReply struct {
	ID            int64
	FeedbackToken uuid.UUID
	Content       string
	CreatedAt     time.Time
}

type ListFeedbackReplyInput struct {
	Page  int
	Limit int
}

type CreateFeedbackReplyInput struct {
	FeedbackToken uuid.UUID
	Content       string
}
