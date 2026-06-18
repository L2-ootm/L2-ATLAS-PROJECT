/**
 * Supabase Client Configuration
 * 
 * Prepara o cliente do Supabase para uso futuro.
 * As credenciais são lidas das variáveis de ambiente.
 * 
 * Para ativar o Supabase:
 * 1. Configure NEXT_PUBLIC_SUPABASE_URL e NEXT_PUBLIC_SUPABASE_ANON_KEY no .env.local
 * 2. Troque as implementações dos repositórios em lib/repositories/index.ts
 * 
 * IMPORTANTE: Este módulo só será utilizado quando a migração para o Supabase
 * estiver completa. Até lá, os repositórios continuam usando SQLite.
 */

import { createClient, SupabaseClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

let _supabase: SupabaseClient | null = null;

/**
 * Retorna o cliente do Supabase (singleton).
 * Lança erro se as credenciais não estiverem configuradas.
 */
export function getSupabaseClient(): SupabaseClient {
  if (_supabase) return _supabase;

  if (!supabaseUrl || !supabaseAnonKey) {
    throw new Error(
      '[Supabase] Missing environment variables: NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY must be set in .env.local'
    );
  }

  _supabase = createClient(supabaseUrl, supabaseAnonKey, {
    auth: {
      persistSession: false, // Server-side: no session persistence needed
    },
  });

  return _supabase;
}

/**
 * Verifica se o Supabase está configurado (variáveis de ambiente presentes).
 */
export function isSupabaseConfigured(): boolean {
  return Boolean(supabaseUrl && supabaseAnonKey);
}
