-- +goose Up
ALTER TABLE user_feedbacks
  ALTER COLUMN email TYPE VARCHAR(255),
  ALTER COLUMN message TYPE TEXT;

-- +goose Down
ALTER TABLE user_feedbacks 
    ALTER COLUMN email TYPE VARCHAR(32),
    ALTER COLUMN message TYPE VARCHAR(255);
