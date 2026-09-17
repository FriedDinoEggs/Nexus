package service

import (
	"context"
	"fmt"
	"strings"

	"go-services/internal/domain"
	"go-services/internal/ierrors"

	"github.com/google/uuid"
)

type FeedbackReplyServiceImpl struct {
	feedbackRepo domain.UserFeedbackRepository
}

func NewFeedbackReplyServiceImpl(feedbackRepo domain.UserFeedbackRepository) *FeedbackReplyServiceImpl {
	return &FeedbackReplyServiceImpl{
		feedbackRepo: feedbackRepo,
	}
}

func (s *FeedbackReplyServiceImpl) CreateReply(ctx context.Context, input domain.CreateFeedbackReplyInput, identity domain.Identity) (domain.FeedbackReply, error) {
	if !identity.IsAdmin() {
		return domain.FeedbackReply{}, ierrors.ErrForbidden
	}

	if strings.TrimSpace(input.Content) == "" {
		return domain.FeedbackReply{}, fmt.Errorf("reply content cannot be empty: %w", ierrors.ErrFeedbackFields)
	}

	return s.feedbackRepo.Replies().Create(ctx, input)
}

func (s *FeedbackReplyServiceImpl) ListReplies(ctx context.Context, input domain.ListFeedbackReplyInput, identity domain.Identity) ([]domain.FeedbackReply, bool, error) {
	if !identity.IsAdmin() {
		return nil, false, ierrors.ErrForbidden
	}

	return s.feedbackRepo.Replies().FindAll(ctx, input)
}

func (s *FeedbackReplyServiceImpl) FindByToken(ctx context.Context, token uuid.UUID) ([]domain.FeedbackReply, error) {
	return s.feedbackRepo.Replies().FindByToken(ctx, token)
}
