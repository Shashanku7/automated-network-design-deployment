-- ============================================================
-- ChatGPT-Style Conversation Persistence Schema
-- PostgreSQL 15+
--
-- Separates:
--   1. User-visible conversation history
--   2. Agent orchestration/execution
--   3. Event streaming/debugging
--   4. Tool execution auditing
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ============================================================
-- ENUMS
-- ============================================================

CREATE TYPE message_role AS ENUM (
    'system',
    'user',
    'assistant',
    'tool'
);

CREATE TYPE task_status AS ENUM (
    'pending',
    'running',
    'completed',
    'failed',
    'cancelled'
);

CREATE TYPE agent_event_type AS ENUM (
    'TOKEN',
    'TOOL_CALL',
    'TOOL_RESULT',
    'FINAL_ANSWER',
    'PHASE_APPROVED',
    'ERROR'
);

-- ============================================================
-- CONVERSATIONS
-- One chat thread within a project
-- ============================================================

CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    project_id UUID NOT NULL,

    title VARCHAR(255),

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_conversations_project
    ON conversations(project_id);

CREATE INDEX idx_conversations_updated
    ON conversations(updated_at DESC);

-- ============================================================
-- MESSAGES
-- Source of truth for chat history
-- ============================================================

CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    conversation_id UUID NOT NULL
        REFERENCES conversations(id)
        ON DELETE CASCADE,

    sequence_no BIGINT NOT NULL,

    role message_role NOT NULL,

    content TEXT NOT NULL,

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX uq_messages_sequence
    ON messages(conversation_id, sequence_no);

CREATE INDEX idx_messages_conversation
    ON messages(conversation_id, created_at);

-- ============================================================
-- AGENT TASKS
-- Represents a single orchestration request
-- ============================================================

CREATE TABLE agent_tasks (
    task_id UUID PRIMARY KEY,

    conversation_id UUID NOT NULL
        REFERENCES conversations(id)
        ON DELETE CASCADE,

    project_id UUID NOT NULL,

    phase INTEGER NOT NULL DEFAULT 0,

    agent_target VARCHAR(100),

    input_context TEXT,

    output TEXT,

    status task_status NOT NULL DEFAULT 'pending',

    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX idx_agent_tasks_conversation
    ON agent_tasks(conversation_id);

CREATE INDEX idx_agent_tasks_project
    ON agent_tasks(project_id);

CREATE INDEX idx_agent_tasks_status
    ON agent_tasks(status);

-- ============================================================
-- AGENT EVENTS
-- Persisted Kafka AgentEvents
-- Useful for replay, debugging, analytics
-- ============================================================

CREATE TABLE agent_events (
    id BIGSERIAL PRIMARY KEY,

    task_id UUID NOT NULL
        REFERENCES agent_tasks(task_id)
        ON DELETE CASCADE,

    project_id UUID NOT NULL,

    agent_name VARCHAR(100) NOT NULL,

    event_type agent_event_type NOT NULL,

    data TEXT,

    payload JSONB,

    is_final BOOLEAN NOT NULL DEFAULT FALSE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_agent_events_task
    ON agent_events(task_id, id);

CREATE INDEX idx_agent_events_project
    ON agent_events(project_id);

CREATE INDEX idx_agent_events_type
    ON agent_events(event_type);

-- ============================================================
-- TOOL CALLS
-- Optional observability for tool executions
-- ============================================================

CREATE TABLE tool_calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    task_id UUID NOT NULL
        REFERENCES agent_tasks(task_id)
        ON DELETE CASCADE,

    tool_name VARCHAR(255) NOT NULL,

    arguments JSONB,

    result JSONB,

    status VARCHAR(32),

    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_tool_calls_task
    ON tool_calls(task_id);

-- ============================================================
-- CONVERSATION MESSAGE VIEW
-- Useful for reconstructing AgentTask.history
-- ============================================================

CREATE VIEW conversation_history AS
SELECT
    c.project_id,
    m.conversation_id,
    m.sequence_no,
    m.role,
    m.content,
    m.created_at
FROM messages m
JOIN conversations c
    ON c.id = m.conversation_id
ORDER BY
    m.conversation_id,
    m.sequence_no;

-- ============================================================
-- TRIGGER TO AUTO-UPDATE conversation.updated_at
-- ============================================================

CREATE OR REPLACE FUNCTION touch_conversation_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE conversations
    SET updated_at = now()
    WHERE id = NEW.conversation_id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_touch_conversation_updated_at
AFTER INSERT ON messages
FOR EACH ROW
EXECUTE FUNCTION touch_conversation_updated_at();

-- ============================================================
-- EXAMPLE HISTORY QUERY
--
-- SELECT role, content
-- FROM messages
-- WHERE conversation_id = :conversation_id
-- ORDER BY sequence_no;
--
-- Maps directly to:
-- AgentTask.history -> List<ChatMessage>
-- ============================================================
