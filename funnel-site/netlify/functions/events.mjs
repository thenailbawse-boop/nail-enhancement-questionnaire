import { makeDeps } from "../../lib/runtime.mjs";
import { eventsHandler } from "../../lib/handlers.mjs";
export default (req) => eventsHandler(req, makeDeps());
export const config = { path: "/api/events" };
