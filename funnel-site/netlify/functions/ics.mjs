import { makeDeps } from "../../lib/runtime.mjs";
import { icsHandler } from "../../lib/handlers.mjs";
export default (req) => icsHandler(req, makeDeps());
export const config = { path: "/api/ics" };
