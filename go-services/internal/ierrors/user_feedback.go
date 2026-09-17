package ierrors

import (
	"net/http"

	"go-services/internal/pkg/code"
)

var (
	ErrFeedbackNotFound      = NewAPIError(http.StatusNotFound, code.FeedbackNotFound, "Feedback record not found", nil, nil)
	ErrFeedbackFields        = NewAPIError(http.StatusBadRequest, code.FeedbackInvalidFields, "Invalid feedback field format", nil, nil)
	ErrDataInconsistent      = NewAPIError(http.StatusInternalServerError, code.FeedbackDataInconsistent, "Feedback data inconsistency detected", nil, nil)
	ErrForbidden             = NewAPIError(http.StatusForbidden, code.Forbidden, "Permission denied", nil, nil)
	ErrFeedbackReplyNotFound = NewAPIError(http.StatusNotFound, code.NotFound, "Feedback reply not found", nil, nil)
)
