-- +goose Up
-- +goose StatementBegin
CREATE TABLE user_feedbacks (
    id BIGSERIAL PRIMARY KEY,

    user_id BIGINT,
    email VARCHAR(32) DEFAULT '' NOT NULL,
    category VARCHAR(32) DEFAULT '' NOT NULL,
    title VARCHAR(32) DEFAULT '' NOT NULL,
    message VARCHAR(255) DEFAULT '' NOT NULL,

    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,

    CONSTRAINT fk_user_feedback
    FOREIGN KEY (user_id)
    REFERENCES core_user (id)
    ON DELETE SET NULL
);

CREATE INDEX idx_user_feedbacks_user_id ON user_feedbacks (user_id);
-- +goose StatementEnd

-- +goose Down
-- +goose StatementBegin

DROP INDEX idx_user_feedbacks_user_id;

DROP TABLE IF EXISTS user_feedbacks CASCADE;
-- +goose StatementEnd
