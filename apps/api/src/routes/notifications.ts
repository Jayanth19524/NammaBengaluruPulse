import { Router, Request, Response } from "express";
import { getRecentNotifications, markRead } from "../../core/notifications";

export const notificationsRouter = Router();

notificationsRouter.get("/", async (_req: Request, res: Response) => {
  const notifications = await getRecentNotifications(20);
  return res.json({ notifications, count: notifications.length });
});

notificationsRouter.patch("/:id/read", async (req: Request, res: Response) => {
  await markRead(req.params.id);
  return res.json({ message: "Marked as read" });
});
