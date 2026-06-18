import { NextResponse } from "next/server";
import { getAllUsageEvents } from "@/lib/db/enterprise";

export async function GET() {
    try {
        const logs = getAllUsageEvents();
        return NextResponse.json({ success: true, logs });
    } catch (error) {
        console.error("Error fetching AI token logs:", error);
        return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
    }
}
