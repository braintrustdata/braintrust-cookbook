// Load .env.local (and .env) before any module constructs an API client.
// Imported first everywhere so BRAINTRUST_API_KEY is set at module-eval time.
import { config } from "dotenv";

config({ path: ".env.local" });
config();
