# Login
psql -h localhost -p 5432 -U cadev
ca@dev

sudo -u postgres psql -p 5439
sudo -u cadev psql -p 5439


# Postgresql
sudo -u postgres psql

# Check Extensions
\d+ chat_conversations

# Create Backup
CREATE TABLE chat_conversations_backup AS SELECT * FROM chat_conversations;

# Rename
ALTER TABLE chat_conversations RENAME TO chat_conversations1;

# Drop existing indexes to avoid conflicts
DROP INDEX IF EXISTS ix_conv_company_id;
DROP INDEX IF EXISTS ix_conv_client_identifier;
DROP INDEX IF EXISTS ix_conv_session_id;
DROP INDEX IF EXISTS ix_conv_sessidcreatedat;


# create table
CREATE TABLE chat_conversations (
    id BIGSERIAL NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    company_id INTEGER NOT NULL,
    message_id VARCHAR(128),
    parent_message_id VARCHAR(128),
    mobile VARCHAR(128) NOT NULL,
    role VARCHAR(20) NOT NULL,
    function_name VARCHAR(128),
    message TEXT NOT NULL,
    request_medium VARCHAR(128),
    request_id VARCHAR(256),
    client_identifier VARCHAR(256),
    client_session_id VARCHAR(256),
    session_id VARCHAR(256) NOT NULL,
    billing_session_id VARCHAR(256),
    message_type VARCHAR(10) NOT NULL,
    message_metadata JSONB,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    deleted_at TIMESTAMP WITH TIME ZONE NULL,
    PRIMARY KEY (company_id, id, created_at) -- Adjusted the order to match typical conventions
) PARTITION BY LIST (company_id);

# Insert all records
INSERT INTO chat_conversations (
    id, created_at, updated_at, company_id, message_id, parent_message_id, mobile, 
    role, function_name, message, request_medium, request_id, client_identifier, 
    client_session_id, session_id, billing_session_id, 
    message_type, message_metadata, is_deleted, is_active, deleted_at
)
SELECT 
    id, created_at, updated_at, company_id, message_id, parent_message_id, mobile, role, function_name, message, request_medium, request_id, client_identifier, client_session_id, 
    session_id, billing_session_id, message_type, message_metadata, is_deleted, is_active, deleted_at
FROM chat_conversations_backup
WHERE company_id IN (7)
AND created_at >= '2024-07-01' 
AND created_at < '2025-08-01';


# Recreate index
CREATE INDEX ix_conv_company_id ON chat_conversations(company_id);
CREATE INDEX ix_conv_client_identifier ON chat_conversations(client_identifier);
CREATE INDEX ix_conv_session_id ON chat_conversations(session_id);
CREATE INDEX ix_conv_sessidcreatedat ON chat_conversations(session_id, created_at);

# Current Companies
- 1
- 2
- 3
- 4
- 5
- 6
- 7
- 8
- 9 
- 10
- 11
- 12
- 13
- 14
- 15


# List Partition
CREATE TABLE chat_conversations_1 PARTITION OF chat_conversations FOR VALUES IN (1) PARTITION BY range (created_at);
CREATE TABLE chat_conversations_2 PARTITION OF chat_conversations FOR VALUES IN (2) PARTITION BY range (created_at);
CREATE TABLE chat_conversations_3 PARTITION OF chat_conversations FOR VALUES IN (3) PARTITION BY range (created_at);
CREATE TABLE chat_conversations_4 PARTITION OF chat_conversations FOR VALUES IN (4) PARTITION BY range (created_at);
CREATE TABLE chat_conversations_5 PARTITION OF chat_conversations FOR VALUES IN (5) PARTITION BY range (created_at);
CREATE TABLE chat_conversations_6 PARTITION OF chat_conversations FOR VALUES IN (6) PARTITION BY range (created_at);
CREATE TABLE chat_conversations_7 PARTITION OF chat_conversations FOR VALUES IN (7) PARTITION BY range (created_at);
CREATE TABLE chat_conversations_8 PARTITION OF chat_conversations FOR VALUES IN (8) PARTITION BY range (created_at);
CREATE TABLE chat_conversations_9 PARTITION OF chat_conversations FOR VALUES IN (9) PARTITION BY range (created_at);
CREATE TABLE chat_conversations_10 PARTITION OF chat_conversations FOR VALUES IN (10) PARTITION BY range (created_at);
CREATE TABLE chat_conversations_11 PARTITION OF chat_conversations FOR VALUES IN (11) PARTITION BY range (created_at);
CREATE TABLE chat_conversations_12 PARTITION OF chat_conversations FOR VALUES IN (12) PARTITION BY range (created_at);
CREATE TABLE chat_conversations_13 PARTITION OF chat_conversations FOR VALUES IN (13) PARTITION BY range (created_at);
CREATE TABLE chat_conversations_14 PARTITION OF chat_conversations FOR VALUES IN (14) PARTITION BY range (created_at);
CREATE TABLE chat_conversations_15 PARTITION OF chat_conversations FOR VALUES IN (15) PARTITION BY range (created_at);




# Create Range Partitions
CREATE TABLE chat_conversations_1_q1_2024 PARTITION OF chat_conversations_1 FOR VALUES FROM ('2024-01-01') TO ('2024-04-01');
CREATE TABLE chat_conversations_1_q2_2024 PARTITION OF chat_conversations_1 FOR VALUES FROM ('2024-04-01') TO ('2024-07-01');
CREATE TABLE chat_conversations_1_q3_2024 PARTITION OF chat_conversations_1 FOR VALUES FROM ('2024-07-01') TO ('2024-10-01');
CREATE TABLE chat_conversations_1_q4_2024 PARTITION OF chat_conversations_1 FOR VALUES FROM ('2024-10-01') TO ('2024-12-31');

CREATE TABLE chat_conversations_1_q1_2025 PARTITION OF chat_conversations_1 FOR VALUES FROM ('2025-01-01') TO ('2025-04-01');
CREATE TABLE chat_conversations_1_q2_2025 PARTITION OF chat_conversations_1 FOR VALUES FROM ('2025-04-01') TO ('2025-07-01');
CREATE TABLE chat_conversations_1_q3_2025 PARTITION OF chat_conversations_1 FOR VALUES FROM ('2025-07-01') TO ('2025-10-01');
CREATE TABLE chat_conversations_1_q4_2025 PARTITION OF chat_conversations_1 FOR VALUES FROM ('2025-10-01') TO ('2025-12-31');

# ----------
CREATE TABLE chat_conversations_2_q1_2024 PARTITION OF chat_conversations_2 FOR VALUES FROM ('2024-01-01') TO ('2024-04-01');
CREATE TABLE chat_conversations_2_q2_2024 PARTITION OF chat_conversations_2 FOR VALUES FROM ('2024-04-01') TO ('2024-07-01');
CREATE TABLE chat_conversations_2_q3_2024 PARTITION OF chat_conversations_2 FOR VALUES FROM ('2024-07-01') TO ('2024-10-01');
CREATE TABLE chat_conversations_2_q4_2024 PARTITION OF chat_conversations_2 FOR VALUES FROM ('2024-10-01') TO ('2024-12-31');

CREATE TABLE chat_conversations_2_q1_2025 PARTITION OF chat_conversations_2 FOR VALUES FROM ('2025-01-01') TO ('2025-04-01');
CREATE TABLE chat_conversations_2_q2_2025 PARTITION OF chat_conversations_2 FOR VALUES FROM ('2025-04-01') TO ('2025-07-01');
CREATE TABLE chat_conversations_2_q3_2025 PARTITION OF chat_conversations_2 FOR VALUES FROM ('2025-07-01') TO ('2025-10-01');
CREATE TABLE chat_conversations_2_q4_2025 PARTITION OF chat_conversations_2 FOR VALUES FROM ('2025-10-01') TO ('2025-12-31');

# ----------
CREATE TABLE chat_conversations_3_q1_2024 PARTITION OF chat_conversations_3 FOR VALUES FROM ('2024-01-01') TO ('2024-04-01');
CREATE TABLE chat_conversations_3_q1_2025 PARTITION OF chat_conversations_3 FOR VALUES FROM ('2025-01-01') TO ('2025-04-01');

CREATE TABLE chat_conversations_3_q2_2024 PARTITION OF chat_conversations_3 FOR VALUES FROM ('2024-04-01') TO ('2024-07-01');
CREATE TABLE chat_conversations_3_q2_2025 PARTITION OF chat_conversations_3 FOR VALUES FROM ('2025-04-01') TO ('2025-07-01');

CREATE TABLE chat_conversations_3_q3_2024 PARTITION OF chat_conversations_3 FOR VALUES FROM ('2024-07-01') TO ('2024-10-01');
CREATE TABLE chat_conversations_3_q3_2025 PARTITION OF chat_conversations_3 FOR VALUES FROM ('2025-07-01') TO ('2025-10-01');

CREATE TABLE chat_conversations_3_q4_2024 PARTITION OF chat_conversations_3 FOR VALUES FROM ('2024-10-01') TO ('2024-12-31');
CREATE TABLE chat_conversations_3_q4_2025 PARTITION OF chat_conversations_3 FOR VALUES FROM ('2025-10-01') TO ('2025-12-31');

# ----------
CREATE TABLE chat_conversations_4_q1_2024 PARTITION OF chat_conversations_4 FOR VALUES FROM ('2024-01-01') TO ('2024-04-01');
CREATE TABLE chat_conversations_4_q1_2025 PARTITION OF chat_conversations_4 FOR VALUES FROM ('2025-01-01') TO ('2025-04-01');

CREATE TABLE chat_conversations_4_q2_2024 PARTITION OF chat_conversations_4 FOR VALUES FROM ('2024-04-01') TO ('2024-07-01');
CREATE TABLE chat_conversations_4_q2_2025 PARTITION OF chat_conversations_4 FOR VALUES FROM ('2025-04-01') TO ('2025-07-01');

CREATE TABLE chat_conversations_4_q3_2024 PARTITION OF chat_conversations_4 FOR VALUES FROM ('2024-07-01') TO ('2024-10-01');
CREATE TABLE chat_conversations_4_q3_2025 PARTITION OF chat_conversations_4 FOR VALUES FROM ('2025-07-01') TO ('2025-10-01');

CREATE TABLE chat_conversations_4_q4_2024 PARTITION OF chat_conversations_4 FOR VALUES FROM ('2024-10-01') TO ('2024-12-31');
CREATE TABLE chat_conversations_4_q4_2025 PARTITION OF chat_conversations_4 FOR VALUES FROM ('2025-10-01') TO ('2025-12-31');

# ----------
CREATE TABLE chat_conversations_5_q1_2024 PARTITION OF chat_conversations_5 FOR VALUES FROM ('2024-01-01') TO ('2024-04-01');
CREATE TABLE chat_conversations_5_q1_2025 PARTITION OF chat_conversations_5 FOR VALUES FROM ('2025-01-01') TO ('2025-04-01');

CREATE TABLE chat_conversations_5_q2_2024 PARTITION OF chat_conversations_5 FOR VALUES FROM ('2024-04-01') TO ('2024-07-01');
CREATE TABLE chat_conversations_5_q2_2025 PARTITION OF chat_conversations_5 FOR VALUES FROM ('2025-04-01') TO ('2025-07-01');

CREATE TABLE chat_conversations_5_q3_2024 PARTITION OF chat_conversations_5 FOR VALUES FROM ('2024-07-01') TO ('2024-10-01');
CREATE TABLE chat_conversations_5_q3_2025 PARTITION OF chat_conversations_5 FOR VALUES FROM ('2025-07-01') TO ('2025-10-01');

CREATE TABLE chat_conversations_5_q4_2024 PARTITION OF chat_conversations_5 FOR VALUES FROM ('2024-10-01') TO ('2024-12-31');
CREATE TABLE chat_conversations_5_q4_2025 PARTITION OF chat_conversations_5 FOR VALUES FROM ('2025-10-01') TO ('2025-12-31');

# ----------
CREATE TABLE chat_conversations_6_q1_2024 PARTITION OF chat_conversations_6 FOR VALUES FROM ('2024-01-01') TO ('2024-04-01');
CREATE TABLE chat_conversations_6_q1_2025 PARTITION OF chat_conversations_6 FOR VALUES FROM ('2025-01-01') TO ('2025-04-01');

CREATE TABLE chat_conversations_6_q2_2024 PARTITION OF chat_conversations_6 FOR VALUES FROM ('2024-04-01') TO ('2024-07-01');
CREATE TABLE chat_conversations_6_q2_2025 PARTITION OF chat_conversations_6 FOR VALUES FROM ('2025-04-01') TO ('2025-07-01');

CREATE TABLE chat_conversations_6_q3_2024 PARTITION OF chat_conversations_6 FOR VALUES FROM ('2024-07-01') TO ('2024-10-01');
CREATE TABLE chat_conversations_6_q3_2025 PARTITION OF chat_conversations_6 FOR VALUES FROM ('2025-07-01') TO ('2025-10-01');

CREATE TABLE chat_conversations_6_q4_2024 PARTITION OF chat_conversations_6 FOR VALUES FROM ('2024-10-01') TO ('2024-12-31');
CREATE TABLE chat_conversations_6_q4_2025 PARTITION OF chat_conversations_6 FOR VALUES FROM ('2025-10-01') TO ('2025-12-31');

# ----------
CREATE TABLE chat_conversations_7_q1_2024 PARTITION OF chat_conversations_7 FOR VALUES FROM ('2024-01-01') TO ('2024-04-01');
CREATE TABLE chat_conversations_7_q1_2025 PARTITION OF chat_conversations_7 FOR VALUES FROM ('2025-01-01') TO ('2025-04-01');

CREATE TABLE chat_conversations_7_q2_2024 PARTITION OF chat_conversations_7 FOR VALUES FROM ('2024-04-01') TO ('2024-07-01');
CREATE TABLE chat_conversations_7_q2_2025 PARTITION OF chat_conversations_7 FOR VALUES FROM ('2025-04-01') TO ('2025-07-01');

CREATE TABLE chat_conversations_7_q3_2024 PARTITION OF chat_conversations_7 FOR VALUES FROM ('2024-07-01') TO ('2024-10-01');
CREATE TABLE chat_conversations_7_q3_2025 PARTITION OF chat_conversations_7 FOR VALUES FROM ('2025-07-01') TO ('2025-10-01');

CREATE TABLE chat_conversations_7_q4_2024 PARTITION OF chat_conversations_7 FOR VALUES FROM ('2024-10-01') TO ('2024-12-31');
CREATE TABLE chat_conversations_7_q4_2025 PARTITION OF chat_conversations_7 FOR VALUES FROM ('2025-10-01') TO ('2025-12-31');

# ----------
CREATE TABLE chat_conversations_8_q1_2024 PARTITION OF chat_conversations_8 FOR VALUES FROM ('2024-01-01') TO ('2024-04-01');
CREATE TABLE chat_conversations_8_q1_2025 PARTITION OF chat_conversations_8 FOR VALUES FROM ('2025-01-01') TO ('2025-04-01');

CREATE TABLE chat_conversations_8_q2_2024 PARTITION OF chat_conversations_8 FOR VALUES FROM ('2024-04-01') TO ('2024-07-01');
CREATE TABLE chat_conversations_8_q2_2025 PARTITION OF chat_conversations_8 FOR VALUES FROM ('2025-04-01') TO ('2025-07-01');

CREATE TABLE chat_conversations_8_q3_2024 PARTITION OF chat_conversations_8 FOR VALUES FROM ('2024-07-01') TO ('2024-10-01');
CREATE TABLE chat_conversations_8_q3_2025 PARTITION OF chat_conversations_8 FOR VALUES FROM ('2025-07-01') TO ('2025-10-01');

CREATE TABLE chat_conversations_8_q4_2024 PARTITION OF chat_conversations_8 FOR VALUES FROM ('2024-10-01') TO ('2024-12-31');
CREATE TABLE chat_conversations_8_q4_2025 PARTITION OF chat_conversations_8 FOR VALUES FROM ('2025-10-01') TO ('2025-12-31');

# ----------

CREATE TABLE chat_conversations_9_q1_2024 PARTITION OF chat_conversations_9 FOR VALUES FROM ('2024-01-01') TO ('2024-04-01');
CREATE TABLE chat_conversations_9_q1_2025 PARTITION OF chat_conversations_9 FOR VALUES FROM ('2025-01-01') TO ('2025-04-01');

CREATE TABLE chat_conversations_9_q2_2024 PARTITION OF chat_conversations_9 FOR VALUES FROM ('2024-04-01') TO ('2024-07-01');
CREATE TABLE chat_conversations_9_q2_2025 PARTITION OF chat_conversations_9 FOR VALUES FROM ('2025-04-01') TO ('2025-07-01');

CREATE TABLE chat_conversations_9_q3_2024 PARTITION OF chat_conversations_9 FOR VALUES FROM ('2024-07-01') TO ('2024-10-01');
CREATE TABLE chat_conversations_9_q3_2025 PARTITION OF chat_conversations_9 FOR VALUES FROM ('2025-07-01') TO ('2025-10-01');

CREATE TABLE chat_conversations_9_q4_2024 PARTITION OF chat_conversations_9 FOR VALUES FROM ('2024-10-01') TO ('2024-12-31');
CREATE TABLE chat_conversations_9_q4_2025 PARTITION OF chat_conversations_9 FOR VALUES FROM ('2025-10-01') TO ('2025-12-31');

# ----------

CREATE TABLE chat_conversations_10_q1_2024 PARTITION OF chat_conversations_10 FOR VALUES FROM ('2024-01-01') TO ('2024-04-01');
CREATE TABLE chat_conversations_10_q1_2025 PARTITION OF chat_conversations_10 FOR VALUES FROM ('2025-01-01') TO ('2025-04-01');

CREATE TABLE chat_conversations_10_q2_2024 PARTITION OF chat_conversations_10 FOR VALUES FROM ('2024-04-01') TO ('2024-07-01');
CREATE TABLE chat_conversations_10_q2_2025 PARTITION OF chat_conversations_10 FOR VALUES FROM ('2025-04-01') TO ('2025-07-01');

CREATE TABLE chat_conversations_10_q3_2024 PARTITION OF chat_conversations_10 FOR VALUES FROM ('2024-07-01') TO ('2024-10-01');
CREATE TABLE chat_conversations_10_q3_2025 PARTITION OF chat_conversations_10 FOR VALUES FROM ('2025-07-01') TO ('2025-10-01');

CREATE TABLE chat_conversations_10_q4_2024 PARTITION OF chat_conversations_10 FOR VALUES FROM ('2024-10-01') TO ('2024-12-31');
CREATE TABLE chat_conversations_10_q4_2025 PARTITION OF chat_conversations_10 FOR VALUES FROM ('2025-10-01') TO ('2025-12-31');

# ----------

CREATE TABLE chat_conversations_11_q1_2024 PARTITION OF chat_conversations_11 FOR VALUES FROM ('2024-01-01') TO ('2024-04-01');
CREATE TABLE chat_conversations_11_q1_2025 PARTITION OF chat_conversations_11 FOR VALUES FROM ('2025-01-01') TO ('2025-04-01');

CREATE TABLE chat_conversations_11_q2_2024 PARTITION OF chat_conversations_11 FOR VALUES FROM ('2024-04-01') TO ('2024-07-01');
CREATE TABLE chat_conversations_11_q2_2025 PARTITION OF chat_conversations_11 FOR VALUES FROM ('2025-04-01') TO ('2025-07-01');

CREATE TABLE chat_conversations_11_q3_2024 PARTITION OF chat_conversations_11 FOR VALUES FROM ('2024-07-01') TO ('2024-10-01');
CREATE TABLE chat_conversations_11_q3_2025 PARTITION OF chat_conversations_11 FOR VALUES FROM ('2025-07-01') TO ('2025-10-01');

CREATE TABLE chat_conversations_11_q4_2024 PARTITION OF chat_conversations_11 FOR VALUES FROM ('2024-10-01') TO ('2024-12-31');
CREATE TABLE chat_conversations_11_q4_2025 PARTITION OF chat_conversations_11 FOR VALUES FROM ('2025-10-01') TO ('2025-12-31');

# ----------

CREATE TABLE chat_conversations_12_q1_2024 PARTITION OF chat_conversations_12 FOR VALUES FROM ('2024-01-01') TO ('2024-04-01');
CREATE TABLE chat_conversations_12_q1_2025 PARTITION OF chat_conversations_12 FOR VALUES FROM ('2025-01-01') TO ('2025-04-01');

CREATE TABLE chat_conversations_12_q2_2024 PARTITION OF chat_conversations_12 FOR VALUES FROM ('2024-04-01') TO ('2024-07-01');
CREATE TABLE chat_conversations_12_q2_2025 PARTITION OF chat_conversations_12 FOR VALUES FROM ('2025-04-01') TO ('2025-07-01');

CREATE TABLE chat_conversations_12_q3_2024 PARTITION OF chat_conversations_12 FOR VALUES FROM ('2024-07-01') TO ('2024-10-01');
CREATE TABLE chat_conversations_12_q3_2025 PARTITION OF chat_conversations_12 FOR VALUES FROM ('2025-07-01') TO ('2025-10-01');

CREATE TABLE chat_conversations_12_q4_2024 PARTITION OF chat_conversations_12 FOR VALUES FROM ('2024-10-01') TO ('2024-12-31');
CREATE TABLE chat_conversations_12_q4_2025 PARTITION OF chat_conversations_12 FOR VALUES FROM ('2025-10-01') TO ('2025-12-31');

# ----------

CREATE TABLE chat_conversations_13_q1_2024 PARTITION OF chat_conversations_13 FOR VALUES FROM ('2024-01-01') TO ('2024-04-01');
CREATE TABLE chat_conversations_13_q1_2025 PARTITION OF chat_conversations_13 FOR VALUES FROM ('2025-01-01') TO ('2025-04-01');

CREATE TABLE chat_conversations_13_q2_2024 PARTITION OF chat_conversations_13 FOR VALUES FROM ('2024-04-01') TO ('2024-07-01');
CREATE TABLE chat_conversations_13_q2_2025 PARTITION OF chat_conversations_13 FOR VALUES FROM ('2025-04-01') TO ('2025-07-01');

CREATE TABLE chat_conversations_13_q3_2024 PARTITION OF chat_conversations_13 FOR VALUES FROM ('2024-07-01') TO ('2024-10-01');
CREATE TABLE chat_conversations_13_q3_2025 PARTITION OF chat_conversations_13 FOR VALUES FROM ('2025-07-01') TO ('2025-10-01');

CREATE TABLE chat_conversations_13_q4_2024 PARTITION OF chat_conversations_13 FOR VALUES FROM ('2024-10-01') TO ('2024-12-31');
CREATE TABLE chat_conversations_13_q4_2025 PARTITION OF chat_conversations_13 FOR VALUES FROM ('2025-10-01') TO ('2025-12-31');

# ----------

CREATE TABLE chat_conversations_14_q1_2024 PARTITION OF chat_conversations_14 FOR VALUES FROM ('2024-01-01') TO ('2024-04-01');
CREATE TABLE chat_conversations_14_q1_2025 PARTITION OF chat_conversations_14 FOR VALUES FROM ('2025-01-01') TO ('2025-04-01');

CREATE TABLE chat_conversations_14_q2_2024 PARTITION OF chat_conversations_14 FOR VALUES FROM ('2024-04-01') TO ('2024-07-01');
CREATE TABLE chat_conversations_14_q2_2025 PARTITION OF chat_conversations_14 FOR VALUES FROM ('2025-04-01') TO ('2025-07-01');

CREATE TABLE chat_conversations_14_q3_2024 PARTITION OF chat_conversations_14 FOR VALUES FROM ('2024-07-01') TO ('2024-10-01');
CREATE TABLE chat_conversations_14_q3_2025 PARTITION OF chat_conversations_14 FOR VALUES FROM ('2025-07-01') TO ('2025-10-01');

CREATE TABLE chat_conversations_14_q4_2024 PARTITION OF chat_conversations_14 FOR VALUES FROM ('2024-10-01') TO ('2024-12-31');
CREATE TABLE chat_conversations_14_q4_2025 PARTITION OF chat_conversations_14 FOR VALUES FROM ('2025-10-01') TO ('2025-12-31');

# ----------

CREATE TABLE chat_conversations_15_q1_2024 PARTITION OF chat_conversations_15 FOR VALUES FROM ('2024-01-01') TO ('2024-04-01');
CREATE TABLE chat_conversations_15_q1_2025 PARTITION OF chat_conversations_15 FOR VALUES FROM ('2025-01-01') TO ('2025-04-01');

CREATE TABLE chat_conversations_15_q2_2024 PARTITION OF chat_conversations_15 FOR VALUES FROM ('2024-04-01') TO ('2024-07-01');
CREATE TABLE chat_conversations_15_q2_2025 PARTITION OF chat_conversations_15 FOR VALUES FROM ('2025-04-01') TO ('2025-07-01');

CREATE TABLE chat_conversations_15_q3_2024 PARTITION OF chat_conversations_15 FOR VALUES FROM ('2024-07-01') TO ('2024-10-01');
CREATE TABLE chat_conversations_15_q3_2025 PARTITION OF chat_conversations_15 FOR VALUES FROM ('2025-07-01') TO ('2025-10-01');

CREATE TABLE chat_conversations_15_q4_2024 PARTITION OF chat_conversations_15 FOR VALUES FROM ('2024-10-01') TO ('2024-12-31');
CREATE TABLE chat_conversations_15_q4_2025 PARTITION OF chat_conversations_15 FOR VALUES FROM ('2025-10-01') TO ('2025-12-31');

# ---------- Change Owner of Table
ALTER TABLE public.chat_conversations_1 OWNER TO cadev;
ALTER TABLE public.chat_conversations_10 OWNER TO cadev;