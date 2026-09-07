package service

import (
	"context"

	"go-services/internal/domain"
)

type UserFeedbackServiceImpl struct {
	repo domain.UserFeedbackRepository
}

func NewUserFeedbackServiceImpl(repo domain.UserFeedbackRepository) *UserFeedbackServiceImpl {
	return &UserFeedbackServiceImpl{
		repo: repo,
	}
}

func (ufs *UserFeedbackServiceImpl) FindAll(ctx context.Context, input domain.ListFeedbackInput, identity domain.Identity) ([]domain.UserFeedback, bool, error) {
	filter := domain.FeedbackFilter{UserID: &identity.UserID}
	if identity.IsAdmin() {
		filter.UserID = nil
	}

	fb, hasNext, err := ufs.repo.FindAll(ctx, input, filter)
	if err != nil {
		return nil, false, err
	}

	return fb[:min(len(fb), input.Limit)], hasNext, nil
}

func (ufs *UserFeedbackServiceImpl) FindByID(ctx context.Context, ID int64, identity domain.Identity) (domain.UserFeedback, error) {
	filter := domain.FeedbackFilter{UserID: &identity.UserID}
	if identity.IsAdmin() {
		filter.UserID = nil
	}

	fb, err := ufs.repo.FindByID(ctx, ID, filter)
	if err != nil {
		return domain.UserFeedback{}, err
	}
	return fb, nil
}

func (ufs *UserFeedbackServiceImpl) Create(ctx context.Context, input domain.CreateFeedbackInput) (domain.UserFeedback, error) {
	fb, err := ufs.repo.Create(ctx, input)
	if err != nil {
		return domain.UserFeedback{}, err
	}

	return fb, nil
}

func (ufs *UserFeedbackServiceImpl) Update(ctx context.Context, ID int64, updateFields domain.UpdateFeedbackInput, identity domain.Identity) (domain.UserFeedback, error) {
	filter := domain.FeedbackFilter{UserID: &identity.UserID}
	if identity.IsAdmin() {
		filter.UserID = nil
	}
	fb, err := ufs.repo.Update(ctx, ID, updateFields, filter)
	if err != nil {
		return domain.UserFeedback{}, err
	}
	return fb, nil
}
