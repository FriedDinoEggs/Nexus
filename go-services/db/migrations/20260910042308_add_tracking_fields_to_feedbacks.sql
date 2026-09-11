-- +goose Up
ALTER TABLE user_feedbacks
ADD COLUMN tracking_token uuid NOT NULL UNIQUE DEFAULT gen_random_uuid();
-- +goose Down
ALTER TABLE user_feedbacks
DROP COLUMN tracking_token;
