package postgres

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"reflect"
	"slices"
	"strconv"
	"strings"
	"time"

	"go-services/internal/domain"
	"go-services/internal/ierrors"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type userFeedbackRepository struct {
	db *pgxpool.Pool
}

func NewUserFeedbackRepository(db *pgxpool.Pool) domain.UserFeedbackRepository {
	return &userFeedbackRepository{
		db: db,
	}
}

var feedbackFieldNameMap = make(map[string]string)

func init() {
	t := reflect.TypeFor[PGUserFeedback]()
	for field := range t.Fields() {
		dbTag := field.Tag.Get("db")
		domainTag := field.Tag.Get("domain")
		if dbTag != "" && dbTag != "-" && domainTag != "" {
			feedbackFieldNameMap[domainTag] = dbTag
		}
	}
}

func (uf *userFeedbackRepository) FindAll(ctx context.Context, input domain.ListFeedbackInput, filter domain.FeedbackFilter) ([]domain.UserFeedback, bool, error) {
	limit := input.Limit + 1
	offset := input.Page * input.Limit
	basequery := `SELECT *
									FROM user_feedbacks`

	var args []any

	query, args := buildBaseQueryWithFilter(basequery, -1, filter)

	args = append(args, limit)
	limitParam := "$" + strconv.Itoa(len(args))
	args = append(args, offset)
	offsetParam := "$" + strconv.Itoa(len(args))

	finalQuery := fmt.Sprintf("%s ORDER BY id DESC LIMIT %s OFFSET %s",
		query, limitParam, offsetParam)

	rows, err := uf.db.Query(ctx, finalQuery, args...)
	if err != nil {
		slog.ErrorContext(ctx, "userFeedback: PostgreSQL FindAll query failed", "error", err, "limit", limit, "offset", offset)
		return nil, false, fmt.Errorf("userFeedback: FindAll failed: %w", err)
	}
	defer rows.Close()

	feedbacks, err := pgx.CollectRows(rows, pgx.RowToStructByName[PGUserFeedback])
	if err != nil {
		slog.ErrorContext(ctx, "userFeedback: PostgreSQL FindAll CollectRows failed", "error", err)
		return nil, false, fmt.Errorf("userFeedback: FindAll CollectRows failed: %w", err)
	}

	userFeedbacks := make([]domain.UserFeedback, len(feedbacks))
	for i, feedback := range feedbacks {
		userFeedbacks[i] = feedback.ToDomain()
	}
	hasNext := len(userFeedbacks) > input.Limit

	return userFeedbacks[:min(len(userFeedbacks), input.Limit)], hasNext, nil
}

func (uf *userFeedbackRepository) FindByID(ctx context.Context, ID int64, filter domain.FeedbackFilter) (domain.UserFeedback, error) {
	basequery := "SELECT * FROM user_feedbacks"

	finalQuery, args := buildBaseQueryWithFilter(basequery, ID, filter)

	rows, err := uf.db.Query(ctx, finalQuery, args...)
	if err != nil {
		slog.ErrorContext(ctx, "userFeedback: PostgreSQL FindByID query failed", "feedback_id", ID, "error", err)
		return domain.UserFeedback{}, err
	}
	defer rows.Close()

	fb, err := pgx.CollectOneRow(rows, pgx.RowToStructByName[PGUserFeedback])
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			slog.WarnContext(ctx, "userFeedback: PostgreSQL FindByID record not found", "feedback_id", ID)
			return domain.UserFeedback{}, fmt.Errorf("feedback not found: %w", ierrors.ErrFeedbackNotFound)
		}
		slog.ErrorContext(ctx, "userFeedback: PostgreSQL FindByID CollectOneRow failed", "feedback_id", ID, "error", err)
		return domain.UserFeedback{}, fmt.Errorf("data anomaly: %w", ierrors.ErrDataInconsistent)
	}
	ufb := fb.ToDomain()
	return ufb, nil
}

func (uf *userFeedbackRepository) Create(ctx context.Context, input domain.CreateFeedbackInput) (domain.UserFeedback, error) {
	pgData := &PGUserFeedback{
		UserID:   input.UserID,
		Email:    input.Email,
		Category: input.Category,
		Title:    input.Title,
		Message:  input.Message,
	}

	query := `INSERT INTO user_feedbacks (user_id, email, category, title, message) 
									VALUES ($1, $2, $3, $4, $5)
									RETURNING *`

	rows, err := uf.db.Query(ctx, query, pgData.UserID, pgData.Email, pgData.Category, pgData.Title, pgData.Message)
	if err != nil {
		slog.ErrorContext(ctx, "userFeedback: PostgreSQL Create query failed", "category", pgData.Category, "title", pgData.Title, "error", err)
		return domain.UserFeedback{}, err
	}
	defer rows.Close()

	insertedData, err := pgx.CollectOneRow(rows, pgx.RowToStructByName[PGUserFeedback])
	if err != nil {
		slog.ErrorContext(ctx, "userFeedback: PostgreSQL Create CollectOneRow failed", "error", err)
		return domain.UserFeedback{}, err
	}

	InsertFeedback := insertedData.ToDomain()
	return InsertFeedback, nil
}

func (uf *userFeedbackRepository) Update(ctx context.Context, ID int64, input domain.UpdateFeedbackInput, filter domain.FeedbackFilter) (domain.UserFeedback, error) {
	domainFields := make(map[string]any)

	if input.Category != nil {
		domainFields["Category"] = *input.Category
	}
	if input.Email != nil {
		domainFields["Email"] = *input.Email
	}
	if input.Message != nil {
		domainFields["Message"] = *input.Message
	}
	if input.Title != nil {
		domainFields["Title"] = *input.Title
	}

	if len(domainFields) == 0 {
		slog.WarnContext(ctx, "userFeedback: Update called with no valid fields", "feedback_id", ID)
		return domain.UserFeedback{}, fmt.Errorf("no valid fields provided for update: %w", ierrors.ErrFeedbackFields)
	}
	domainFields["UpdatedAt"] = time.Now().UTC()

	// 使用經過排序的keys建構query string，以利pgx execution plan 快取
	keys := make([]string, 0, len(domainFields))
	for k := range domainFields {
		keys = append(keys, k)
	}
	slices.Sort(keys)

	var updateFields []string
	var args []any
	argsCounter := 1

	for _, fieldKey := range keys {
		fieldValue := domainFields[fieldKey]

		dbColumnName, exists := feedbackFieldNameMap[fieldKey]
		if !exists {
			slog.WarnContext(ctx, "userFeedback: Update invalid field name", "field_name", fieldKey, "feedback_id", ID)
			return domain.UserFeedback{}, fmt.Errorf("invalid field name %s: %w", fieldKey, ierrors.ErrFeedbackFields)
		}

		fieldAssignments := fmt.Sprintf("%s = $%d", dbColumnName, argsCounter)

		updateFields = append(updateFields, fieldAssignments)
		args = append(args, fieldValue)
		argsCounter++
	}

	setClause := strings.Join(updateFields, ", ")
	args = append(args, ID)

	query := ""
	if filter.UserID != nil {
		query = fmt.Sprintf("UPDATE user_feedbacks SET %s WHERE id = $%d AND user_id = $%d RETURNING *", setClause, argsCounter, argsCounter+1)
		args = append(args, *filter.UserID)
	} else {
		query = fmt.Sprintf("UPDATE user_feedbacks SET %s WHERE id = $%d RETURNING *", setClause, argsCounter)
	}

	rows, err := uf.db.Query(ctx, query, args...)
	if err != nil {
		slog.ErrorContext(ctx, "userFeedback: PostgreSQL Update query execution failed", "feedback_id", ID, "error", err)
		return domain.UserFeedback{}, err
	}
	defer rows.Close()

	updatedPGFeedback, err := pgx.CollectOneRow(rows, pgx.RowToStructByName[PGUserFeedback])
	if err != nil {
		if errors.Is(err, pgx.ErrNoRows) {
			uid := any(nil)
			if filter.UserID != nil {
				uid = *filter.UserID
			}
			slog.WarnContext(ctx, "userFeedback: PostgreSQL Update record not found or unauthorized", "feedback_id", ID, "user_id", uid)
			return domain.UserFeedback{}, fmt.Errorf("feedback not found: %w", ierrors.ErrFeedbackNotFound)
		}
		slog.ErrorContext(ctx, "userFeedback: PostgreSQL Update CollectOneRow failed", "feedback_id", ID, "error", err)
		return domain.UserFeedback{}, err
	}

	updatedDomainFeedback := updatedPGFeedback.ToDomain()

	return updatedDomainFeedback, nil
}

func buildBaseQueryWithFilter(baseQuery string, id int64, filter domain.FeedbackFilter) (string, []any) {
	var clauses []string
	var args []any

	if id > 0 {
		args = append(args, id)
		clauses = append(clauses, "id = $"+strconv.Itoa(len(args)))
	}

	if filter.UserID != nil {
		args = append(args, *filter.UserID)
		clauses = append(clauses, "user_id = $"+strconv.Itoa(len(args)))
	}

	finalQuery := baseQuery
	if len(clauses) > 0 {
		finalQuery += " WHERE " + strings.Join(clauses, " AND ")
	}

	return finalQuery, args
}
