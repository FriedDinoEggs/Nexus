package response

import (
	"errors"
	"net/http"

	"go-services/internal/ierrors"
	"go-services/internal/pkg/code"

	"github.com/gin-gonic/gin"
)

// APIResponse represents the standardized JSON response contract
type APIResponse struct {
	Code      code.Code `json:"code"`
	Message   string    `json:"message"`
	Data      any       `json:"data,omitempty"`
	TraceID   *string   `json:"traceId,omitempty"`
	Timestamp *int64    `json:"timestamp,omitempty"`
}

// getTraceID extracts the TraceID set in gin.Context by TraceMiddleware
func getTraceID(c *gin.Context) *string {
	if val, exists := c.Get("trace_id"); exists {
		if s, ok := val.(string); ok && s != "" {
			return &s
		}
	}
	return nil
}

// Success returns HTTP 200 OK response
func Success(c *gin.Context, data any) {
	c.JSON(http.StatusOK, APIResponse{
		Code:      code.Success,
		Message:   "Success",
		Data:      data,
		TraceID:   getTraceID(c),
		Timestamp: nil,
	})
}

// Created returns HTTP 201 Created response
func Created(c *gin.Context, data any) {
	c.JSON(http.StatusCreated, APIResponse{
		Code:      code.Success,
		Message:   "Created successfully",
		Data:      data,
		TraceID:   getTraceID(c),
		Timestamp: nil,
	})
}

// BadRequest returns HTTP 400 Bad Request response with default BAD_REQUEST code
func BadRequest(c *gin.Context, message string) {
	c.JSON(http.StatusBadRequest, APIResponse{
		Code:      code.BadRequest,
		Message:   message,
		TraceID:   getTraceID(c),
		Timestamp: nil,
	})
}

// BadRequestWithCode returns HTTP 400 Bad Request response with a specific business code
func BadRequestWithCode(c *gin.Context, bizCode code.Code, message string) {
	c.JSON(http.StatusBadRequest, APIResponse{
		Code:      bizCode,
		Message:   message,
		TraceID:   getTraceID(c),
		Timestamp: nil,
	})
}

// NotFound returns HTTP 404 Not Found response
func NotFound(c *gin.Context, message string) {
	c.JSON(http.StatusNotFound, APIResponse{
		Code:      code.NotFound,
		Message:   message,
		TraceID:   getTraceID(c),
		Timestamp: nil,
	})
}

// InternalError returns HTTP 500 Internal Server Error response
func InternalError(c *gin.Context, message string) {
	c.JSON(http.StatusInternalServerError, APIResponse{
		Code:      code.InternalServerError,
		Message:   message,
		TraceID:   getTraceID(c),
		Timestamp: nil,
	})
}

// FailWithError automatically maps APIError or domain errors to standardized APIResponse
func FailWithError(c *gin.Context, err error) {
	var apiErr *ierrors.APIError
	if errors.As(err, &apiErr) {
		c.JSON(apiErr.HTTPStatus, APIResponse{
			Code:      apiErr.BizCode,
			Message:   apiErr.Message,
			TraceID:   getTraceID(c),
			Timestamp: nil,
		})
		return
	}

	// Default fallback for unhandled internal server errors
	c.JSON(http.StatusInternalServerError, APIResponse{
		Code:      code.InternalServerError,
		Message:   "Internal server error",
		TraceID:   getTraceID(c),
		Timestamp: nil,
	})
}
