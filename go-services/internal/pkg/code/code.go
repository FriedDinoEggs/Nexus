package code

type Code string

const (
	Success             Code = "SUCCESS"
	BadRequest          Code = "BAD_REQUEST"
	InvalidParams       Code = "INVALID_PARAMS"
	Unauthorized        Code = "UNAUTHORIZED"
	Forbidden           Code = "FORBIDDEN"
	NotFound            Code = "NOT_FOUND"
	InternalServerError Code = "INTERNAL_SERVER_ERROR"

	FeedbackNotFound         Code = "USER_FEEDBACK_NOT_FOUND"
	FeedbackInvalidFields    Code = "USER_FEEDBACK_INVALID_FIELDS"
	FeedbackDataInconsistent Code = "USER_FEEDBACK_DATA_INCONSISTENT"

	JWTExpired        Code = "USER_JWT_EXPIRED"
	JWTIvalid         Code = "USER_JWT_INVALID"
	JWTUndefinedError Code = "USER_JWT_UNDEFINED"
)
