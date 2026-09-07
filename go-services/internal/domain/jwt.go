package domain

import "time"

type UserCliams struct {
	TokenType string
	UserID    int64
	JTI       string
	ExpiresAt time.Time
	IssuedAt  time.Time
}

type UserJWTVerifier interface {
	Verify(tokenStr string) (UserCliams, error)
}
