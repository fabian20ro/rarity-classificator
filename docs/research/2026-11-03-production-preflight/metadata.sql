BEGIN READ ONLY;
SELECT jsonb_build_object(
 'captured_at',clock_timestamp(), 'database',current_database(),'current_user',current_user,'session_user',session_user,
 'server_version',current_setting('server_version'),'read_only',current_setting('transaction_read_only'),
 'row_security',current_setting('row_security'),
 'ledger_schema',to_regnamespace('classificator_private')::text,
 'ledger_table',to_regclass('classificator_private.human_correction_receipts')::text,
 'roles',(SELECT jsonb_agg(jsonb_build_object('name',rolname,'login',rolcanlogin,'superuser',rolsuper,'bypassrls',rolbypassrls,'inherit',rolinherit,'words_select',has_table_privilege(oid,'public.words','SELECT'),'words_update',has_table_privilege(oid,'public.words','UPDATE'),'schema_usage',has_schema_privilege(oid,'public','USAGE')) ORDER BY rolname) FROM pg_roles),
 'memberships',(SELECT jsonb_agg(jsonb_build_object('member',m.rolname,'role',r.rolname,'inherit',am.inherit_option,'set',am.set_option)) FROM pg_auth_members am JOIN pg_roles m ON m.oid=am.member JOIN pg_roles r ON r.oid=am.roleid),
 'table',(SELECT jsonb_build_object('owner',pg_get_userbyid(relowner),'kind',relkind,'rls',relrowsecurity,'force_rls',relforcerowsecurity,'acl',relacl,'partition',relispartition) FROM pg_class WHERE oid='public.words'::regclass),
 'columns',(SELECT jsonb_agg(jsonb_build_object('name',attname,'type',format_type(atttypid,atttypmod),'not_null',attnotnull,'generated',attgenerated,'identity',attidentity) ORDER BY attnum) FROM pg_attribute WHERE attrelid='public.words'::regclass AND attnum>0 AND NOT attisdropped),
 'policies',(SELECT coalesce(jsonb_agg(to_jsonb(p)), '[]'::jsonb) FROM pg_policies p WHERE schemaname='public' AND tablename='words'),
 'triggers',(SELECT coalesce(jsonb_agg(jsonb_build_object('name',t.tgname,'internal',t.tgisinternal,'enabled',t.tgenabled,'definition',pg_get_triggerdef(t.oid),'function',p.oid::regprocedure::text,'security_definer',p.prosecdef,'function_owner',pg_get_userbyid(p.proowner),'function_config',p.proconfig,'function_definition',CASE WHEN NOT t.tgisinternal THEN pg_get_functiondef(p.oid) END)),'[]'::jsonb) FROM pg_trigger t JOIN pg_proc p ON p.oid=t.tgfoid WHERE t.tgrelid='public.words'::regclass),
 'constraints',(SELECT coalesce(jsonb_agg(jsonb_build_object('name',conname,'table',conrelid::regclass::text,'references',confrelid::regclass::text,'type',contype,'definition',pg_get_constraintdef(oid),'validated',convalidated,'deferrable',condeferrable,'deferred',condeferred)),'[]'::jsonb) FROM pg_constraint WHERE conrelid='public.words'::regclass OR confrelid='public.words'::regclass),
 'rules',(SELECT coalesce(jsonb_agg(jsonb_build_object('name',rulename,'definition',pg_get_ruledef(oid))),'[]'::jsonb) FROM pg_rewrite WHERE ev_class='public.words'::regclass),
 'inheritance',(SELECT coalesce(jsonb_agg(jsonb_build_object('child',inhrelid::regclass::text,'parent',inhparent::regclass::text)),'[]'::jsonb) FROM pg_inherits WHERE inhrelid='public.words'::regclass OR inhparent='public.words'::regclass)
) AS preflight;
ROLLBACK;
