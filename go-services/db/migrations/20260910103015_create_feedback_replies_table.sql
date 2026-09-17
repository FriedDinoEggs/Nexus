-- +goose Up
CREATE TABLE feedback_replies (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    feedback_token uuid NOT NULL REFERENCES user_feedbacks(tracking_token) ON DELETE CASCADE,
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_feedback_replies_feedback_id ON feedback_replies(feedback_token);


-- +goose Down
DROP TABLE feedback_replies;
