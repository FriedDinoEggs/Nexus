package dto

import (
	"time"

	"github.com/google/uuid"
)

type UpdateFeedbackRequest struct {
	Email    *string `json:"email" binding:"omitempty,email"`
	Category *string `json:"category" binding:"omitempty,max=32"`
	Title    *string `json:"title" binding:"omitempty,max=32"`
	Message  *string `json:"message" binding:"omitempty,max=5000"`
}

type CreateFeedbackRequest struct {
	Email    string `json:"email" binding:"required,email,max=255"`
	Category string `json:"category" binding:"required,max=32"`
	Title    string `json:"title" binding:"required,max=32"`
	Message  string `json:"message" binding:"required,max=5000"`
}

type ListFeedbackRequest struct {
	Page  int `form:"page" binding:"omitempty,gte=1"`
	Limit int `form:"limit" binding:"omitempty,gte=1,lte=200"`
}

type UserFeedbackResponse struct {
	ID            int64     `json:"id"`
	UserID        *int64    `json:"userId"`
	TrackingToken uuid.UUID `json:"trackingToken"`
	Email         string    `json:"email"`
	Category      string    `json:"category"`
	Title         string    `json:"title"`
	Message       string    `json:"message"`

	CreatedAt time.Time `json:"createdAt"`
	UpdatedAt time.Time `json:"updatedAt"`
}

type ListFeedbackResponse struct {
	Items   []UserFeedbackResponse `json:"items"`
	HasNext bool                   `json:"hasNext"`
	Page    int                    `json:"page"`
	Limit   int                    `json:"limit"`
}

type UpdateFeedbackResponse = UserFeedbackResponse
