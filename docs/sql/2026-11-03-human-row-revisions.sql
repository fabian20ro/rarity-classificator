-- Explicit installation prerequisite; never installed by the runtime.
-- Requires the private receipt schema. Execute only with separate deployment authorization.
-- Existing incompatible objects deliberately fail. Owner/DDL/backup administrators are trusted.
BEGIN;
LOCK TABLE public.words IN ACCESS EXCLUSIVE MODE;
CREATE SEQUENCE classificator_private.words_revision_seq AS bigint NO CYCLE CACHE 1;
REVOKE ALL ON SEQUENCE classificator_private.words_revision_seq FROM PUBLIC;
CREATE TABLE classificator_private.words_revision_contract (
    singleton boolean PRIMARY KEY CHECK (singleton),
    epoch uuid NOT NULL DEFAULT pg_catalog.gen_random_uuid()
) USING heap;
INSERT INTO classificator_private.words_revision_contract (singleton) VALUES (true);
REVOKE ALL ON TABLE classificator_private.words_revision_contract FROM PUBLIC;
ALTER TABLE public.words ADD COLUMN classificator_revision bigint;
CREATE FUNCTION classificator_private.assign_word_revision() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $revision$
BEGIN
    NEW.classificator_revision := pg_catalog.nextval('classificator_private.words_revision_seq'::pg_catalog.regclass);
    RETURN NEW;
END;
$revision$;
REVOKE ALL ON FUNCTION classificator_private.assign_word_revision() FROM PUBLIC;
CREATE TRIGGER classificator_word_revision BEFORE INSERT OR UPDATE ON public.words
FOR EACH ROW EXECUTE FUNCTION classificator_private.assign_word_revision();
ALTER TABLE public.words ENABLE ALWAYS TRIGGER classificator_word_revision;
-- Bootstrap tokens only; preserve every existing score. Trigger ignores supplied tokens.
UPDATE public.words SET classificator_revision = 0;
ALTER TABLE public.words ALTER COLUMN classificator_revision SET NOT NULL;
ALTER TABLE public.words ADD CONSTRAINT classificator_revision_positive CHECK (classificator_revision > 0);
CREATE UNIQUE INDEX classificator_word_revision_unique ON public.words (classificator_revision);
COMMIT;
-- Executor: SELECT/UPDATE words, schema USAGE, SELECT contract, SELECT/INSERT/UPDATE receipts.
-- No executor access to sequence, trigger function, DDL, or contract writes.
-- Ordinary writers receive new revisions through the trigger; do not disable it/reset sequence.
