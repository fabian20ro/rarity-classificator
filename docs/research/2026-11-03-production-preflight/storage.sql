BEGIN READ ONLY;
SELECT jsonb_build_object('captured_at',clock_timestamp(),'read_only',current_setting('transaction_read_only'),'access_method',a.amname,'default_table_access_method',current_setting('default_table_access_method'),'extensions',(SELECT jsonb_agg(jsonb_build_object('name',extname,'version',extversion)) FROM pg_extension WHERE extname IN ('orioledb','pgcrypto')),'row_security_active',row_security_active('public.words')) AS storage FROM pg_class c JOIN pg_am a ON a.oid=c.relam WHERE c.oid='public.words'::regclass;
ROLLBACK;
