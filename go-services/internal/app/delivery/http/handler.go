package http

import (
	"context"

	"go-services/internal/domain"

	"github.com/google/uuid"
)

type UserFeedbackService interface {
	FindAll(ctx context.Context, input domain.ListFeedbackInput, identity domain.Identity) ([]domain.UserFeedback, bool, error)
	FindByID(ctx context.Context, ID int64, identity domain.Identity) (domain.UserFeedback, error)
	Create(ctx context.Context, input domain.CreateFeedbackInput) (domain.UserFeedback, error)
	Update(ctx context.Context, ID int64, updateFields domain.UpdateFeedbackInput, identity domain.Identity) (domain.UserFeedback, error)
}

type FeedbackReplyService interface {
	CreateReply(ctx context.Context, input domain.CreateFeedbackReplyInput, identity domain.Identity) (domain.FeedbackReply, error)
	ListReplies(ctx context.Context, input domain.ListFeedbackReplyInput, identity domain.Identity) ([]domain.FeedbackReply, bool, error)
	FindByToken(ctx context.Context, token uuid.UUID) ([]domain.FeedbackReply, error)
}

type Handler struct {
	feedbackServices UserFeedbackService
	replyService     FeedbackReplyService
}

func NewHandler(s UserFeedbackService, rs FeedbackReplyService) *Handler {
	return &Handler{
		feedbackServices: s,
		replyService:     rs,
	}
}
