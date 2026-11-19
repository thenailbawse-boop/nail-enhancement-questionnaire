// Runs every 15 minutes: 24-hour reminder, 1-hour reminder, next-day follow-up/replay.
import { makeDeps } from "../../lib/runtime.mjs";
import { runReminders } from "../../lib/handlers.mjs";
export default async () => {
  const log = await runReminders(makeDeps());
  if (log.length) console.log("sent", log.join(", "));
};
export const config = { schedule: "*/15 * * * *" };
