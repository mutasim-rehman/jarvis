import type { APIRoute } from "astro";
import { google } from "googleapis";
import nodemailer from "nodemailer";

export const prerender = false;

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

/** Returns the title of the first sheet tab (handles any sheet name). */
async function getFirstSheetTitle(
  sheets: ReturnType<typeof google.sheets>,
  spreadsheetId: string,
): Promise<string> {
  const meta = await sheets.spreadsheets.get({
    spreadsheetId,
    fields: "sheets.properties.title",
  });
  return meta.data.sheets?.[0]?.properties?.title ?? "Sheet1";
}

async function ensureHeaders(
  sheets: ReturnType<typeof google.sheets>,
  spreadsheetId: string,
  tab: string,
) {
  const range = `${tab}!A:D`;
  const res = await sheets.spreadsheets.values.get({ spreadsheetId, range });
  if ((res.data.values ?? []).length === 0) {
    await sheets.spreadsheets.values.append({
      spreadsheetId,
      range,
      valueInputOption: "USER_ENTERED",
      requestBody: { values: [HEADERS] },
    });
  }
}

async function isDuplicate(
  sheets: ReturnType<typeof google.sheets>,
  spreadsheetId: string,
  tab: string,
  email: string,
): Promise<boolean> {
  const range = `${tab}!A:D`;
  const res = await sheets.spreadsheets.values.get({ spreadsheetId, range });
  const rows = res.data.values ?? [];
  return rows.slice(1).some((r) => (r[2] ?? "").toLowerCase() === email.toLowerCase());
}

function buildEmailHtml(name: string, email: string): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>You're on the JARVIS waitlist</title>
</head>
<body style="margin:0;padding:0;background:#050505;font-family:'Segoe UI',system-ui,-apple-system,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="background:#050505;">
    <tr>
      <td align="center" style="padding:56px 24px 48px;">
        <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="max-width:520px;">

          <!-- Wordmark -->
          <tr>
            <td style="padding-bottom:36px;">
              <span style="font-size:11px;font-weight:700;letter-spacing:0.22em;text-transform:uppercase;color:#f07a1f;font-family:'Segoe UI',system-ui,sans-serif;">JARVIS</span>
            </td>
          </tr>

          <!-- Card -->
          <tr>
            <td style="background:linear-gradient(145deg,rgba(255,255,255,0.045),rgba(255,255,255,0.01));border:1px solid rgba(255,255,255,0.09);border-radius:16px;padding:40px 36px;">

              <p style="margin:0 0 10px;font-size:10px;font-weight:700;letter-spacing:0.2em;text-transform:uppercase;color:#f07a1f;font-family:'Segoe UI',system-ui,sans-serif;">Waitlist confirmed</p>

              <h1 style="margin:0 0 18px;font-size:26px;font-weight:700;letter-spacing:-0.02em;color:#ffffff;line-height:1.25;font-family:'Segoe UI',system-ui,sans-serif;">
                You're on the list, ${name}.
              </h1>

              <p style="margin:0 0 20px;font-size:15px;color:#b39b86;line-height:1.7;font-family:'Segoe UI',system-ui,sans-serif;">
                We'll reach out to <strong style="color:#f7efe8;">${email}</strong> when early access opens.
                In the meantime, JARVIS is quietly getting smarter.
              </p>

              <!-- Divider -->
              <table width="100%" cellpadding="0" cellspacing="0" role="presentation">
                <tr><td style="border-top:1px solid rgba(255,255,255,0.07);padding-top:24px;padding-bottom:4px;"></td></tr>
              </table>

              <p style="margin:0 0 14px;font-size:11px;font-weight:600;letter-spacing:0.14em;text-transform:uppercase;color:#b39b86;font-family:'Segoe UI',system-ui,sans-serif;">What JARVIS does</p>

              <table cellpadding="0" cellspacing="0" role="presentation" style="width:100%;">
                <tr><td style="padding:5px 0;font-size:13px;color:#b39b86;line-height:1.55;font-family:'Segoe UI',system-ui,sans-serif;"><span style="color:#f07a1f;margin-right:8px;">→</span>Understands your goals and builds a plan</td></tr>
                <tr><td style="padding:5px 0;font-size:13px;color:#b39b86;line-height:1.55;font-family:'Segoe UI',system-ui,sans-serif;"><span style="color:#f07a1f;margin-right:8px;">→</span>Runs multi-step automations with live status</td></tr>
                <tr><td style="padding:5px 0;font-size:13px;color:#b39b86;line-height:1.55;font-family:'Segoe UI',system-ui,sans-serif;"><span style="color:#f07a1f;margin-right:8px;">→</span>Works across desktop, mobile &amp; Raspberry Pi</td></tr>
                <tr><td style="padding:5px 0;font-size:13px;color:#b39b86;line-height:1.55;font-family:'Segoe UI',system-ui,sans-serif;"><span style="color:#f07a1f;margin-right:8px;">→</span>Connects Google, Spotify, files, and your workflows</td></tr>
              </table>

            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding-top:28px;text-align:center;">
              <p style="margin:0;font-size:11px;color:rgba(179,155,134,0.45);line-height:1.6;font-family:'Segoe UI',system-ui,sans-serif;">
                You received this because you joined the JARVIS waitlist.<br />
                Questions? <a href="mailto:jarvis.mutasim@gmail.com" style="color:#ffb36b;text-decoration:none;">jarvis.mutasim@gmail.com</a>
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>`;
}

async function sendConfirmationEmail(toName: string, toEmail: string) {
  const transporter = nodemailer.createTransport({
    host: import.meta.env.SMTP_HOST ?? "smtp.gmail.com",
    port: Number(import.meta.env.SMTP_PORT ?? 465),
    secure: (import.meta.env.SMTP_SECURE ?? "true") === "true",
    auth: {
      user: import.meta.env.SMTP_USER,
      pass: import.meta.env.SMTP_PASS,
    },
  });

  await transporter.sendMail({
    from: `"${import.meta.env.SMTP_APP_NAME ?? "JARVIS"}" <${import.meta.env.SMTP_USER}>`,
    to: toEmail,
    subject: "You're on the JARVIS waitlist",
    html: buildEmailHtml(toName, toEmail),
  });
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
    const tab = await getFirstSheetTitle(sheets, sheetId);

    await ensureHeaders(sheets, sheetId, tab);

    const alreadyIn = await isDuplicate(sheets, sheetId, tab, email);
    if (alreadyIn) {
      // Still fire the email so they get a reminder, but don't re-add
      sendConfirmationEmail(name, email).catch((e) =>
        console.error("[waitlist] email error (existing):", e),
      );
      return json({ success: true, existing: true });
    }

    const range = `${tab}!A:D`;
    await sheets.spreadsheets.values.append({
      spreadsheetId: sheetId,
      range,
      valueInputOption: "USER_ENTERED",
      requestBody: {
        values: [[new Date().toISOString(), name, email.toLowerCase(), "hub"]],
      },
    });

    // Fire-and-forget — don't block the response on email delivery
    sendConfirmationEmail(name, email).catch((e) =>
      console.error("[waitlist] email error:", e),
    );

    return json({ success: true });
  } catch (err) {
    console.error("[waitlist] error:", err);
    return json({ error: "Could not save your entry. Please try again." }, 500);
  }
};
