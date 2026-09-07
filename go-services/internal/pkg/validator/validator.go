package validator

import (
	"errors"
	"net/http"
	"reflect"
	"strings"

	"go-services/internal/ierrors"
	"go-services/internal/pkg/code"

	govalidator "github.com/go-playground/validator/v10"
)

func ParseValidationError(err error, requestObject any) map[string]string {
	var errs govalidator.ValidationErrors

	if !errors.As(err, &errs) {
		return map[string]string{"error": "invalid request format"}
	}
	result := make(map[string]string)
	t := reflect.TypeOf(requestObject)
	if t.Kind() == reflect.Pointer {
		t = t.Elem()
	}

	for _, f := range errs {
		rawFieldName := f.Field()
		fieldName := rawFieldName

		if idx := strings.IndexAny(rawFieldName, ".["); idx != -1 {
			fieldName = rawFieldName[:idx]
		}

		if structField, ok := t.FieldByName(fieldName); ok {
			tag := structField.Tag.Get("json")
			if tag == "" {
				tag = structField.Tag.Get("form")
			}
			if tag != "" {
				fieldName = strings.Split(tag, ",")[0]
			}
		}

		switch f.Tag() {
		case "required":
			result[fieldName] = "This field is required."
		case "email":
			result[fieldName] = "Invalid email format."
		case "min":
			result[fieldName] = "The length is less than the minimum value " + f.Param()
		case "max":
			result[fieldName] = "The length exceeds the maximum value " + f.Param()
		case "gte":
			result[fieldName] = "Must be greater than or equal to " + f.Param()
		case "lte":
			result[fieldName] = "Must be less than or equal to " + f.Param()
		default:
			result[fieldName] = "Field validation error: " + f.Tag()
		}
	}
	return result
}

func NewValidationError(bizCode code.Code, message string, details map[string]string) *ierrors.APIError {
	return ierrors.NewAPIError(http.StatusBadRequest, bizCode, message, nil, details)
}
