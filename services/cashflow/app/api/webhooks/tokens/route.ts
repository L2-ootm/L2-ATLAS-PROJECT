import { NextResponse } from "next/server";
import { logUsageEvent } from "@/lib/db/enterprise";
import { generateId } from "@/lib/utils";

export async function POST(request: Request) {
    try {
        const body = await request.json();

        // Basic validation
        if (!body.client_id) {
            // fallback para o campo antigo caso ainda enviem
            if (body.clientId) {
                body.client_id = body.clientId;
            } else {
                return NextResponse.json({ error: "client_id is required" }, { status: 400 });
            }
        }
        
        if (!body.event_type) {
            body.event_type = "api_call";
        }

        // Save the log in the new usage_events table
        const id = generateId();
        
        logUsageEvent({
            id,
            client_id: body.client_id,
            user_id: body.user_id,
            session_id: body.session_id,
            event_type: body.event_type,
            plan_at_time: body.plan_at_time,
            route: body.route,
            model_provider: body.model_provider,
            model_name: body.model || body.model_name || "unknown",
            input_tokens: body.tokensPrompt || body.input_tokens || 0,
            output_tokens: body.tokensCompletion || body.output_tokens || 0,
            cache_hit_tokens: body.cache_hit_tokens || 0,
            cache_miss_tokens: body.cache_miss_tokens || 0,
            tool_calls: body.tool_calls || 0,
            search_requests: body.search_requests || 0,
            retrieval_chunks: body.retrieval_chunks || 0,
            cost_usd: body.costUsd || body.cost_usd || 0,
            cost_brl: body.cost_brl || 0,
            revenue_attributed_brl: body.revenue_attributed_brl || 0,
            margin_attributed_brl: body.margin_attributed_brl || 0,
            metadata_json: body.metadata_json ? JSON.stringify(body.metadata_json) : undefined
        });

        return NextResponse.json({ success: true, eventId: id }, { status: 201 });

    } catch (error) {
        console.error("Error processing AI token webhook:", error);
        return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
    }
}
