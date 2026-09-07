package ierrors

import (
	"net/http"

	"go-services/internal/pkg/code"
)

var (
	ErrInvalidToken = NewAPIError(http.StatusBadRequest, code.JWTIvalid, "Invalid JWT", nil, nil)
	ErrExpiredToken = NewAPIError(http.StatusUnauthorized, code.JWTExpired, "JWT expired", nil, nil)
)
