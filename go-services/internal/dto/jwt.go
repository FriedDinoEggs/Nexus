package dto

import "github.com/golang-jwt/jwt/v5"

type UserClaims struct {
	TokenType string `json:"token_type"`
	UserID    string `json:"user_id"`
	jwt.RegisteredClaims
}
