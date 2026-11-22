import { useQuery } from "@tanstack/react-query";
import { Notification } from "../types";

async function fetchNotifications(): Promise<Notification[]> {
  const res = await fetch("/api/notifications");
  if (!res.ok) return [];
  const data = (await res.json()) as { notifications: Notification[] };
  return data.notifications ?? [];
}

export function useNotifications() {
  return useQuery({
    queryKey: ["notifications"],
    queryFn: fetchNotifications,
    refetchInterval: 30_000,
    staleTime: 15_000,
  });
}
