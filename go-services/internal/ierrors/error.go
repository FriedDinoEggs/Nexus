package ierrors

import (
	"encoding/json"
	"fmt"

	"go-services/internal/pkg/code"
)

type APIError struct {
	HTTPStatus int
	BizCode    code.Code
	Message    string
	RawErr     error
	Details    map[string]string
}

func (e *APIError) Error() string {
	if e.RawErr != nil {
		return fmt.Sprintf("%s: %v", e.Message, e.RawErr)
	}
	return e.Message
}

func (e *APIError) MarshalJSON() ([]byte, error) {
	return json.Marshal(struct {
		BizCode code.Code         `json:"biz_code"`
		Message string            `json:"message"`
		Details map[string]string `json:"details,omitempty"`
	}{
		BizCode: e.BizCode,
		Message: e.Error(),
		Details: e.Details,
	})
}

func NewAPIError(httpStatus int, bizCode code.Code, message string, rawErr error, details map[string]string) *APIError {
	return &APIError{
		HTTPStatus: httpStatus,
		BizCode:    bizCode,
		Message:    message,
		RawErr:     rawErr,
		Details:    details,
	}
}
