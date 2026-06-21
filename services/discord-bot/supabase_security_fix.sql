-- =============================================================================
-- FIX: Function Search Path Mutable (Security Warning)
-- =============================================================================
-- This forces the function to execute specifically in the 'public' schema,
-- preventing search_path hijacking attacks.

ALTER FUNCTION public.check_node_status SET search_path = public;
ALTER FUNCTION public.wp_sync_analytics SET search_path = public;
ALTER FUNCTION public.log_event SET search_path = public;
ALTER FUNCTION public.trigger_log_user_created SET search_path = public;
ALTER FUNCTION public.trigger_log_user_updated SET search_path = public;
ALTER FUNCTION public.trigger_log_commerce SET search_path = public;
ALTER FUNCTION public.trigger_log_config_change SET search_path = public;
ALTER FUNCTION public.trigger_log_blob_change SET search_path = public;
ALTER FUNCTION public.trigger_log_security_action SET search_path = public;
ALTER FUNCTION public.check_ip_status SET search_path = public;
ALTER FUNCTION public.auto_ban_honeypot_trigger SET search_path = public;
ALTER FUNCTION public.trigger_log_crm_change SET search_path = public;

-- =============================================================================
-- FIX: Permissive RLS Policies (TRUE)
-- =============================================================================
-- The previous policies allowed ANYONE (anon/authenticated) to insert.
-- We restrict this to the 'service_role' (your bot's backend key) only.

-- Drop old policies (if they exist with these names)
DROP POLICY IF EXISTS "Service role can insert audit logs" ON public.audit_logs;
DROP POLICY IF EXISTS "Agents can emit traces" ON public.sys_trace_stream;

-- Create secure policies
CREATE POLICY "Service role can insert audit logs"
ON public.audit_logs
FOR INSERT
TO service_role
WITH CHECK (true);

CREATE POLICY "Agents can emit traces"
ON public.sys_trace_stream
FOR INSERT
TO service_role
WITH CHECK (true);

-- =============================================================================
-- NOTE: Password Protection
-- =============================================================================
-- For the "Leaked Password Protection" warning, you must enable this manually
-- in the Supabase Dashboard:
-- Go to Authentication -> Security -> Password Protection -> Enable "Leaked Password Protection"
