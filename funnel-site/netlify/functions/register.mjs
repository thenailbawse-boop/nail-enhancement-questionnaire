import { makeDeps } from "../../lib/runtime.mjs";
import { registerHandler } from "../../lib/handlers.mjs";
export default (req) => registerHandler(req, makeDeps());
export const config = { path: "/api/register" };
