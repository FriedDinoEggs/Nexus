package http

import (
	"log/slog"
	"strconv"

	"go-services/internal/domain"
	"go-services/internal/dto"
	"go-services/internal/pkg/code"
	"go-services/internal/pkg/response"
	"go-services/internal/pkg/validator"

	"github.com/gin-gonic/gin"
	"github.com/jinzhu/copier"
)

func getIdentity(c *gin.Context) domain.Identity {
	if val, exists := c.Get("identity"); exists {
		if iden, ok := val.(domain.Identity); ok {
			return iden
		}
	}
	return domain.Identity{}
}

func (ufh *Handler) GetUserFeedback(c *gin.Context) {
	ctx := c.Request.Context()
	idStr := c.Param("id")
	id, err := strconv.ParseInt(idStr, 10, 64)
	if err != nil || id <= 0 {
		slog.WarnContext(ctx, "GetUserFeedback: invalid feedback ID format", "id_param", idStr)
		response.BadRequestWithCode(c, code.InvalidParams, "Invalid ID format")
		return
	}

	identity := getIdentity(c)
	var uf domain.UserFeedback
	uf, err = ufh.feedbackServices.FindByID(ctx, id, identity)
	if err != nil {
		slog.WarnContext(ctx, "GetUserFeedback: failed to get feedback", "feedback_id", id, "user_id", identity.UserID, "is_admin", identity.IsAdmin(), "error", err)
		response.FailWithError(c, err)
		return
	}

	var res dto.UserFeedbackResponse
	if err := copier.Copy(&res, &uf); err != nil {
		slog.ErrorContext(ctx, "GetUserFeedback: response transformation failed", "feedback_id", id, "error", err)
		response.InternalError(c, "Data transformation failed: "+err.Error())
		return
	}

	slog.DebugContext(ctx, "GetUserFeedback: feedback retrieved successfully", "feedback_id", uf.ID, "user_id", identity.UserID)
	response.Success(c, res)
}

func (ufh *Handler) ListUserFeedback(c *gin.Context) {
	reqCtx := c.Request.Context()
	var req dto.ListFeedbackRequest
	var err error
	if err = c.ShouldBindQuery(&req); err != nil {
		slog.WarnContext(reqCtx, "ListUserFeedback: invalid query parameters", "error", err)
		errDetails := validator.ParseValidationError(err, req)
		apiErrs := validator.NewValidationError(code.InvalidParams, "Parameter validation error", errDetails)
		c.JSON(apiErrs.HTTPStatus, apiErrs)
		return
	}

	page := req.Page
	if page <= 0 {
		page = 1
	}
	limit := req.Limit
	if limit <= 0 {
		limit = 10
	}

	identity := getIdentity(c)
	inputData := domain.ListFeedbackInput{
		Page:  page - 1,
		Limit: limit,
	}

	var hasNext bool
	var feedbacks []domain.UserFeedback
	feedbacks, hasNext, err = ufh.feedbackServices.FindAll(reqCtx, inputData, identity)
	if err != nil {
		slog.ErrorContext(reqCtx, "ListUserFeedback: failed to list feedbacks", "user_id", identity.UserID, "is_admin", identity.IsAdmin(), "page", page, "limit", limit, "error", err)
		response.FailWithError(c, err)
		return
	}

	var resList []dto.UserFeedbackResponse
	if err := copier.Copy(&resList, &feedbacks); err != nil {
		slog.ErrorContext(reqCtx, "ListUserFeedback: response transformation failed", "error", err)
		response.InternalError(c, "Data transformation failed: "+err.Error())
		return
	}
	if resList == nil {
		resList = []dto.UserFeedbackResponse{}
	}
	resp := dto.ListFeedbackResponse{
		Items:   resList,
		HasNext: hasNext,
		Limit:   limit,
		Page:    page,
	}

	slog.DebugContext(reqCtx, "ListUserFeedback: feedbacks retrieved successfully", "user_id", identity.UserID, "is_admin", identity.IsAdmin(), "page", page, "limit", limit, "count", len(resList))
	response.Success(c, resp)
}

func (ufh *Handler) CreateUserFeedback(c *gin.Context) {
	reqCtx := c.Request.Context()
	var req dto.CreateFeedbackRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		slog.WarnContext(reqCtx, "CreateUserFeedback: invalid JSON payload", "error", err)
		errDetails := validator.ParseValidationError(err, req)
		apiErrs := validator.NewValidationError(code.InvalidParams, "Parameter validation error", errDetails)
		c.JSON(apiErrs.HTTPStatus, apiErrs)
		return
	}

	identity := getIdentity(c)
	var inputData domain.CreateFeedbackInput
	if err := copier.Copy(&inputData, &req); err != nil {
		slog.WarnContext(reqCtx, "CreateUserFeedback: input mapping failed", "error", err)
		response.BadRequest(c, err.Error())
		return
	}

	if identity.UserID > 0 {
		inputData.UserID = &identity.UserID
	} else {
		inputData.UserID = nil
	}

	uf, err := ufh.feedbackServices.Create(reqCtx, inputData)
	if err != nil {
		slog.ErrorContext(reqCtx, "CreateUserFeedback: failed to create feedback", "user_id", identity.UserID, "category", inputData.Category, "title", inputData.Title, "error", err)
		response.FailWithError(c, err)
		return
	}

	var res dto.UserFeedbackResponse
	if err := copier.Copy(&res, &uf); err != nil {
		slog.ErrorContext(reqCtx, "CreateUserFeedback: response transformation failed", "feedback_id", uf.ID, "error", err)
		response.InternalError(c, "Data transformation failed: "+err.Error())
		return
	}

	slog.InfoContext(reqCtx, "CreateUserFeedback: feedback created successfully", "feedback_id", uf.ID, "user_id", identity.UserID, "category", uf.Category, "is_anonymous", identity.UserID == 0)
	response.Created(c, res)
}

func (ufh *Handler) UpdateUserFeedback(ctx *gin.Context) {
	reqCtx := ctx.Request.Context()
	idStr := ctx.Param("id")
	id, err := strconv.ParseInt(idStr, 10, 64)
	if err != nil || id <= 0 {
		slog.WarnContext(reqCtx, "UpdateUserFeedback: invalid feedback ID format", "id_param", idStr)
		response.BadRequestWithCode(ctx, code.InvalidParams, "Invalid ID format")
		return
	}

	var req dto.UpdateFeedbackRequest
	if err := ctx.ShouldBindJSON(&req); err != nil {
		slog.WarnContext(reqCtx, "UpdateUserFeedback: invalid JSON payload", "feedback_id", id, "error", err)
		errDetails := validator.ParseValidationError(err, req)
		apiErrs := validator.NewValidationError(code.InvalidParams, "Parameter validation error", errDetails)
		ctx.JSON(apiErrs.HTTPStatus, apiErrs)
		return
	}

	var inputData domain.UpdateFeedbackInput
	if err := copier.Copy(&inputData, &req); err != nil {
		slog.WarnContext(reqCtx, "UpdateUserFeedback: input mapping failed", "feedback_id", id, "error", err)
		response.BadRequest(ctx, err.Error())
		return
	}

	identity := getIdentity(ctx)
	uf, err := ufh.feedbackServices.Update(reqCtx, id, inputData, identity)
	if err != nil {
		slog.WarnContext(reqCtx, "UpdateUserFeedback: failed to update feedback", "feedback_id", id, "user_id", identity.UserID, "error", err)
		response.FailWithError(ctx, err)
		return
	}

	var responseData dto.UserFeedbackResponse
	if err := copier.Copy(&responseData, &uf); err != nil {
		slog.ErrorContext(reqCtx, "UpdateUserFeedback: response transformation failed", "feedback_id", id, "error", err)
		response.InternalError(ctx, "Data transformation failed: "+err.Error())
		return
	}

	slog.InfoContext(reqCtx, "UpdateUserFeedback: feedback updated successfully", "feedback_id", uf.ID, "user_id", identity.UserID)
	response.Success(ctx, responseData)
}
