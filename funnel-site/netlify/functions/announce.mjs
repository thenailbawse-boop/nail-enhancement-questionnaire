import { makeDeps } from "../../lib/runtime.mjs";
import { announceHandler } from "../../lib/handlers.mjs";
export default (req) => announceHandler(req, makeDeps());
export const config = { path: "/api/announce" };
