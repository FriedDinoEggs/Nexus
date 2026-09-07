package service

import (
	"errors"
	"fmt"
	"log/slog"
	"strconv"

	"go-services/internal/domain"
	"go-services/internal/dto"
	"go-services/internal/ierrors"

	"github.com/golang-jwt/jwt/v5"
)

type jwtVerifierService struct {
	secretKey []byte
}

func NewJwtVerifierService(secrect string) domain.UserJWTVerifier {
	return &jwtVerifierService{
		secretKey: []byte(secrect),
	}
}

func (j *jwtVerifierService) Verify(tokenString string) (domain.UserCliams, error) {
	token, err := jwt.ParseWithClaims(tokenString, &dto.UserClaims{}, func(token *jwt.Token) (any, error) {
		if _, ok := token.Method.(*jwt.SigningMethodHMAC); !ok {
			return nil, fmt.Errorf("unexcepted singing method: %v", token.Header["alg"])
		}
		return j.secretKey, nil
	})
	if err != nil {
		if errors.Is(err, jwt.ErrTokenExpired) {
			return domain.UserCliams{}, ierrors.ErrExpiredToken
		}
		slog.Warn("JWT verify error: " + err.Error())
		return domain.UserCliams{}, ierrors.ErrInvalidToken
	}
	if claims, ok := token.Claims.(*dto.UserClaims); ok && token.Valid {
		if claims.TokenType != "access" {
			return domain.UserCliams{}, ierrors.ErrInvalidToken
		}

		userID, _ := strconv.ParseInt(claims.UserID, 10, 64)
		return domain.UserCliams{
			TokenType: claims.TokenType,
			UserID:    userID,
			JTI:       claims.ID,
			ExpiresAt: claims.ExpiresAt.Time,
			IssuedAt:  claims.IssuedAt.Time,
		}, nil
	}

	return domain.UserCliams{}, ierrors.ErrInvalidToken
}
