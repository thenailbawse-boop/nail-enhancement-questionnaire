import { makeDeps } from "../../lib/runtime.mjs";
import { unsubscribeHandler } from "../../lib/handlers.mjs";
export default (req) => unsubscribeHandler(req, makeDeps());
export const config = { path: "/api/unsubscribe" };
