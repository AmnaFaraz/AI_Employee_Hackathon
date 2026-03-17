-- ============================================================
-- Customer Success Digital FTE — PostgreSQL CRM Schema
-- Requires: pgvector extension
-- ============================================================

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================================
-- ENUMS
-- ============================================================

CREATE TYPE channel_type AS ENUM ('EMAIL', 'WHATSAPP', 'WEB_FORM');
CREATE TYPE ticket_status AS ENUM ('OPEN', 'IN_PROGRESS', 'ESCALATED', 'RESOLVED', 'CLOSED');
CREATE TYPE ticket_priority AS ENUM ('LOW', 'MEDIUM', 'HIGH', 'URGENT');
CREATE TYPE message_role AS ENUM ('CUSTOMER', 'AGENT', 'SYSTEM');
CREATE TYPE identifier_type AS ENUM ('EMAIL', 'PHONE', 'USER_ID', 'WHATSAPP_ID');

-- ============================================================
-- CUSTOMERS
-- Master customer record (cross-channel identity hub)
-- ============================================================

CREATE TABLE customers (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    display_name    VARCHAR(255),
    primary_email   VARCHAR(320) UNIQUE,
    primary_phone   VARCHAR(50),
    company         VARCHAR(255),
    plan            VARCHAR(100) DEFAULT 'free',
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_customers_primary_email ON customers(primary_email);
CREATE INDEX idx_customers_primary_phone ON customers(primary_phone);
CREATE INDEX idx_customers_company      ON customers(company);
CREATE INDEX idx_customers_metadata     ON customers USING gin(metadata);

-- ============================================================
-- CUSTOMER IDENTIFIERS
-- Links external IDs (per channel) to a single customer
-- ============================================================

CREATE TABLE customer_identifiers (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    customer_id     UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    identifier_type identifier_type NOT NULL,
    identifier_value VARCHAR(500) NOT NULL,
    channel         channel_type,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(identifier_type, identifier_value)
);

CREATE INDEX idx_customer_identifiers_customer ON customer_identifiers(customer_id);
CREATE INDEX idx_customer_identifiers_value    ON customer_identifiers(identifier_value);

-- ============================================================
-- CONVERSATIONS
-- A thread per customer per channel session
-- ============================================================

CREATE TABLE conversations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    customer_id     UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    channel         channel_type NOT NULL,
    channel_thread_id VARCHAR(500),        -- Gmail thread ID, Twilio conversation SID, etc.
    subject         VARCHAR(500),
    status          VARCHAR(50) DEFAULT 'ACTIVE',
    metadata        JSONB DEFAULT '{}',
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_message_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at        TIMESTAMPTZ
);

CREATE INDEX idx_conversations_customer  ON conversations(customer_id);
CREATE INDEX idx_conversations_channel   ON conversations(channel);
CREATE INDEX idx_conversations_thread    ON conversations(channel_thread_id);
CREATE INDEX idx_conversations_status    ON conversations(status);
CREATE INDEX idx_conversations_last_msg  ON conversations(last_message_at DESC);

-- ============================================================
-- MESSAGES
-- Individual messages within conversations; stores embeddings
-- ============================================================

CREATE TABLE messages (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    customer_id     UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    role            message_role NOT NULL,
    content         TEXT NOT NULL,
    content_vector  vector(1536),           -- OpenAI text-embedding-3-small
    channel         channel_type NOT NULL,
    channel_message_id VARCHAR(500),        -- External message ID for deduplication
    metadata        JSONB DEFAULT '{}',
    processing_ms   INTEGER,                -- Agent processing time
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_messages_conversation   ON messages(conversation_id);
CREATE INDEX idx_messages_customer       ON messages(customer_id);
CREATE INDEX idx_messages_created        ON messages(created_at DESC);
CREATE INDEX idx_messages_channel_msgid  ON messages(channel_message_id);
-- Vector index for semantic search (HNSW for low latency)
CREATE INDEX idx_messages_vector         ON messages USING hnsw (content_vector vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ============================================================
-- TICKETS
-- Support tickets linked to conversations
-- ============================================================

CREATE TABLE tickets (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticket_number   SERIAL UNIQUE,
    customer_id     UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
    subject         VARCHAR(500) NOT NULL,
    description     TEXT,
    status          ticket_status NOT NULL DEFAULT 'OPEN',
    priority        ticket_priority NOT NULL DEFAULT 'MEDIUM',
    channel         channel_type NOT NULL,
    assigned_to     VARCHAR(255),           -- Human agent email if escalated
    escalation_reason TEXT,
    tags            TEXT[] DEFAULT '{}',
    metadata        JSONB DEFAULT '{}',
    resolved_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tickets_customer        ON tickets(customer_id);
CREATE INDEX idx_tickets_conversation    ON tickets(conversation_id);
CREATE INDEX idx_tickets_status          ON tickets(status);
CREATE INDEX idx_tickets_priority        ON tickets(priority);
CREATE INDEX idx_tickets_created         ON tickets(created_at DESC);
CREATE INDEX idx_tickets_number          ON tickets(ticket_number);
CREATE INDEX idx_tickets_tags            ON tickets USING gin(tags);

-- ============================================================
-- KNOWLEDGE BASE
-- Product documentation chunks with vector embeddings
-- ============================================================

CREATE TABLE knowledge_base (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title           VARCHAR(500) NOT NULL,
    content         TEXT NOT NULL,
    content_vector  vector(1536) NOT NULL,   -- OpenAI text-embedding-3-small
    category        VARCHAR(100),
    tags            TEXT[] DEFAULT '{}',
    source_url      VARCHAR(1000),
    is_active       BOOLEAN DEFAULT TRUE,
    view_count      INTEGER DEFAULT 0,
    helpful_count   INTEGER DEFAULT 0,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_kb_category   ON knowledge_base(category);
CREATE INDEX idx_kb_active     ON knowledge_base(is_active);
CREATE INDEX idx_kb_tags       ON knowledge_base USING gin(tags);
-- HNSW vector index for sub-millisecond retrieval
CREATE INDEX idx_kb_vector     ON knowledge_base USING hnsw (content_vector vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
-- Full-text search fallback
CREATE INDEX idx_kb_fts        ON knowledge_base USING gin(to_tsvector('english', title || ' ' || content));

-- ============================================================
-- AGENT METRICS
-- Per-request performance and quality tracking
-- ============================================================

CREATE TABLE agent_metrics (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    message_id          UUID REFERENCES messages(id) ON DELETE SET NULL,
    ticket_id           UUID REFERENCES tickets(id) ON DELETE SET NULL,
    channel             channel_type NOT NULL,
    processing_ms       INTEGER NOT NULL,       -- Time from receipt to response dispatch
    kb_hits             INTEGER DEFAULT 0,       -- Number of KB articles retrieved
    was_escalated       BOOLEAN DEFAULT FALSE,
    escalation_reason   VARCHAR(255),
    confidence_score    FLOAT,                  -- Agent self-assessed confidence 0.0-1.0
    customer_satisfied  BOOLEAN,                -- From follow-up survey
    tokens_used         INTEGER,
    model_used          VARCHAR(100),
    error_occurred      BOOLEAN DEFAULT FALSE,
    error_message       TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_metrics_channel      ON agent_metrics(channel);
CREATE INDEX idx_metrics_escalated    ON agent_metrics(was_escalated);
CREATE INDEX idx_metrics_created      ON agent_metrics(created_at DESC);
CREATE INDEX idx_metrics_processing   ON agent_metrics(processing_ms);

-- ============================================================
-- TRIGGER: auto-update updated_at columns
-- ============================================================

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_customers_updated_at
    BEFORE UPDATE ON customers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_tickets_updated_at
    BEFORE UPDATE ON tickets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_kb_updated_at
    BEFORE UPDATE ON knowledge_base
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- VIEWS
-- ============================================================

-- Open ticket summary per customer
CREATE VIEW v_customer_open_tickets AS
SELECT
    c.id AS customer_id,
    c.display_name,
    c.primary_email,
    COUNT(t.id)          AS open_ticket_count,
    MAX(t.created_at)    AS latest_ticket_at,
    ARRAY_AGG(t.priority ORDER BY t.created_at DESC) AS priorities
FROM customers c
LEFT JOIN tickets t ON t.customer_id = c.id AND t.status NOT IN ('RESOLVED', 'CLOSED')
GROUP BY c.id, c.display_name, c.primary_email;

-- Daily agent performance summary
CREATE VIEW v_daily_metrics AS
SELECT
    DATE(created_at)            AS day,
    channel,
    COUNT(*)                    AS total_requests,
    AVG(processing_ms)          AS avg_processing_ms,
    MAX(processing_ms)          AS max_processing_ms,
    SUM(CASE WHEN was_escalated THEN 1 ELSE 0 END)      AS escalations,
    ROUND(
        SUM(CASE WHEN was_escalated THEN 1 ELSE 0 END)::NUMERIC / COUNT(*) * 100, 2
    )                           AS escalation_rate_pct,
    SUM(CASE WHEN error_occurred THEN 1 ELSE 0 END)     AS errors,
    AVG(confidence_score)       AS avg_confidence
FROM agent_metrics
GROUP BY DATE(created_at), channel
ORDER BY day DESC, channel;
