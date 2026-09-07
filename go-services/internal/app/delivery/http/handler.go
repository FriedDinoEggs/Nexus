package http

import (
	"context"

	"go-services/internal/domain"
)

type UserFeedbackService interface {
	FindAll(ctx context.Context, input domain.ListFeedbackInput, identity domain.Identity) ([]domain.UserFeedback, bool, error)
	FindByID(ctx context.Context, ID int64, identity domain.Identity) (domain.UserFeedback, error)
	Create(ctx context.Context, input domain.CreateFeedbackInput) (domain.UserFeedback, error)
	Update(ctx context.Context, ID int64, updateFields domain.UpdateFeedbackInput, identity domain.Identity) (domain.UserFeedback, error)
}

type Handler struct {
	feedbackServices UserFeedbackService
}

func NewHandler(s UserFeedbackService) *Handler {
	return &Handler{feedbackServices: s}
}
