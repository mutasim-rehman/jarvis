import type { APIRoute } from "astro";
import { google } from "googleapis";

export const prerender = false;

const SHEET_RANGE = "Waitlist!A:D";
const HEADERS = ["Timestamp", "Name", "Email", "Source"];

function json(body: object, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function isValidEmail(email: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

async function getSheetsClient() {
  const raw = import.meta.env.Google_Service_Account_JSON ?? "";
  if (!raw) throw new Error("Google_Service_Account_JSON not set");
  const creds = JSON.parse(raw);

  const auth = new google.auth.JWT({
    email: creds.client_email,
    key: creds.private_key,
    scopes: ["https://www.googleapis.com/auth/spreadsheets"],
  });

  return google.sheets({ version: "v4", auth });
}

async function ensureHeaders(sheets: ReturnType<typeof google.sheets>, sheetId: string) {
  const res = await sheets.spreadsheets.values.get({
    spreadsheetId: sheetId,
    range: SHEET_RANGE,
  });
  const rows = res.data.values ?? [];
  if (rows.length === 0) {
    await sheets.spreadsheets.values.append({
      spreadsheetId: sheetId,
      range: SHEET_RANGE,
      valueInputOption: "USER_ENTERED",
      requestBody: { values: [HEADERS] },
    });
  }
}

async function isDuplicate(
  sheets: ReturnType<typeof google.sheets>,
  sheetId: string,
  email: string,
) {
  const res = await sheets.spreadsheets.values.get({
    spreadsheetId: sheetId,
    range: SHEET_RANGE,
  });
  const rows = res.data.values ?? [];
  return rows.slice(1).some((row) => (row[2] ?? "").toLowerCase() === email.toLowerCase());
}

export const POST: APIRoute = async ({ request }) => {
  let body: { name?: string; email?: string };
  try {
    body = await request.json();
  } catch {
    return json({ error: "Invalid request body." }, 400);
  }

  const name = (body.name ?? "").trim();
  const email = (body.email ?? "").trim();

  if (!name) return json({ error: "Name is required." }, 400);
  if (!email || !isValidEmail(email)) return json({ error: "A valid email is required." }, 400);

  const sheetId = import.meta.env.WATLIST_SHEET_ID ?? "";
  if (!sheetId) return json({ error: "Server configuration error." }, 500);

  try {
    const sheets = await getSheetsClient();

    await ensureHeaders(sheets, sheetId);

    const alreadyIn = await isDuplicate(sheets, sheetId, email);
    if (alreadyIn) {
      // Return success so we don't reveal whether an email is on the list
      return json({ success: true, existing: true });
    }

    await sheets.spreadsheets.values.append({
      spreadsheetId: sheetId,
      range: SHEET_RANGE,
      valueInputOption: "USER_ENTERED",
      requestBody: {
        values: [[new Date().toISOString(), name, email.toLowerCase(), "hub"]],
      },
    });

    return json({ success: true });
  } catch (err) {
    console.error("[waitlist] Sheets error:", err);
    return json({ error: "Could not save your entry. Please try again." }, 500);
  }
};
