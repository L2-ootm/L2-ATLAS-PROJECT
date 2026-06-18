"use client";

import { useRouter, useSearchParams } from "next/navigation";
import MonthSelector from "./MonthSelector";

export default function ServerMonthSelector({ selectedMonth, selectedYear }: { selectedMonth: number; selectedYear: number }) {
  const router = useRouter();
  const searchParams = useSearchParams();

  const monthStr = selectedMonth.toString().padStart(2, '0');
  const value = `${selectedYear}-${monthStr}`;

  const handleChange = (newValue: string) => {
    const [year, month] = newValue.split("-");
    const params = new URLSearchParams(searchParams?.toString() || "");
    params.set("month", month);
    params.set("year", year);
    router.push(`?${params.toString()}`);
  };

  return <MonthSelector value={value} onChange={handleChange} />;
}
