-- Add missing actions column to chat_messages to match ORM model.
-- Safe to run multiple times.

BEGIN;

ALTER TABLE chat_messages
    ADD COLUMN IF NOT EXISTS actions JSON;

COMMIT;
