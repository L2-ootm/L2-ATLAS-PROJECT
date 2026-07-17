import { getSupabaseClient } from '../supabase';

export interface UsageCalculationOptions {
  modelId: string;
  inputTokens: number;
  outputTokens: number;
  cacheHitTokens?: number;
  cacheMissTokens?: number;
  fxRateUsdBrl?: number; // Optional, defaults to env or static 5.50
}

export interface UsageCalculationResult {
  costUsd: number;
  costBrl: number;
  appliedFxRate: number;
  modelFound: boolean;
}

/**
 * Calculates the absolute cost of an AI usage event based on the rate cards in the database.
 */
export async function calculateUsageCost(options: UsageCalculationOptions): Promise<UsageCalculationResult> {
  const {
    modelId,
    inputTokens,
    outputTokens,
    cacheHitTokens = 0,
    cacheMissTokens = 0,
  } = options;

  // Default FX rate to 5.50 if not provided or in env
  const fxRate = options.fxRateUsdBrl || parseFloat(process.env.FX_RATE_USD_BRL || '5.50');

  const supabase = getSupabaseClient();

  const { data: rateCard, error } = await supabase
    .from('model_rate_cards')
    .select('*')
    .eq('id', modelId)
    .single();

  if (error || !rateCard) {
    // Fallback: Model not found. Assume a standard blended rate to not lose tracking entirely.
    // E.g., $1.00 per 1M input, $2.00 per 1M output.
    const fallbackInputPrice = 1.0;
    const fallbackOutputPrice = 2.0;

    const fallbackCostUsd = ((inputTokens / 1_000_000) * fallbackInputPrice) +
                            ((outputTokens / 1_000_000) * fallbackOutputPrice);

    return {
      costUsd: fallbackCostUsd,
      costBrl: fallbackCostUsd * fxRate,
      appliedFxRate: fxRate,
      modelFound: false,
    };
  }

  // Rate Card Math
  let inputCostUsd = 0;

  // If cache data is explicitly provided, we use the granular caching pricing
  if (cacheHitTokens > 0 || cacheMissTokens > 0) {
    const cacheHitCost = (cacheHitTokens / 1_000_000) * rateCard.cache_hit_price_per_1m_usd;
    const cacheMissCost = (cacheMissTokens / 1_000_000) * rateCard.input_price_per_1m_usd; // Normal input

    // Some providers charge for cache writes (Anthropic).
    // This is complex to track per request, so we assume cache misses are just standard input for now.
    inputCostUsd = cacheHitCost + cacheMissCost;
  } else {
    // Standard input pricing
    inputCostUsd = (inputTokens / 1_000_000) * rateCard.input_price_per_1m_usd;
  }

  const outputCostUsd = (outputTokens / 1_000_000) * rateCard.output_price_per_1m_usd;

  const totalCostUsd = inputCostUsd + outputCostUsd;

  return {
    costUsd: totalCostUsd,
    costBrl: totalCostUsd * fxRate,
    appliedFxRate: fxRate,
    modelFound: true,
  };
}
