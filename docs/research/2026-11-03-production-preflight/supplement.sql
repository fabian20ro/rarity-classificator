BEGIN READ ONLY;
SELECT jsonb_build_object(
 'captured_at',clock_timestamp(),'read_only',current_setting('transaction_read_only'),
 'default_acls',(SELECT coalesce(jsonb_agg(jsonb_build_object('owner',pg_get_userbyid(defaclrole),'schema',n.nspname,'object_type',defaclobjtype,'acl',defaclacl)),'[]'::jsonb) FROM pg_default_acl d LEFT JOIN pg_namespace n ON n.oid=d.defaclnamespace WHERE pg_get_userbyid(defaclrole) IN ('postgres','service_role','supabase_admin')),
 'event_triggers',(SELECT coalesce(jsonb_agg(jsonb_build_object('name',evtname,'event',evtevent,'enabled',evtenabled,'tags',evttags,'owner',pg_get_userbyid(evtowner),'function',p.oid::regprocedure::text,'security_definer',p.prosecdef,'definition',pg_get_functiondef(p.oid))),'[]'::jsonb) FROM pg_event_trigger t JOIN pg_proc p ON p.oid=t.evtfoid),
 'column_privileges',(SELECT coalesce(jsonb_agg(to_jsonb(c)),'[]'::jsonb) FROM information_schema.column_privileges c WHERE table_schema='public' AND table_name='words' AND column_name IN ('id','word','type','rarity_level')),
 'indexes',(SELECT jsonb_agg(jsonb_build_object('name',indexrelid::regclass::text,'valid',indisvalid,'ready',indisready,'definition',pg_get_indexdef(indexrelid))) FROM pg_index WHERE indrelid='public.words'::regclass)
) AS preflight;
ROLLBACK;
