import { makeDeps } from "../../lib/runtime.mjs";
import { registrantsHandler } from "../../lib/handlers.mjs";
export default (req) => registrantsHandler(req, makeDeps());
export const config = { path: "/api/registrants" };
