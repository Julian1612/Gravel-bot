/**
 * Gravel Deal Bot — Telegram-Webhook-Empfaenger (Cloudflare Worker).
 *
 * Einziger Zweck: Telegram schickt hier per Webhook jedes Update (Nachricht,
 * Button-Klick) sofort rein; der Worker reicht es unveraendert per
 * repository_dispatch an GitHub weiter, wo .github/workflows/telegram-update.yml
 * es sofort verarbeitet — ohne auf den naechsten Scan-Cron zu warten.
 *
 * Der Worker selbst enthaelt keine Bot-Logik. Er ist bewusst dumm gehalten:
 * pruefen (Secret-Token), weiterreichen, fertig. Siehe
 * docs/telegram-webhook-setup.md fuer die Einrichtung Schritt fuer Schritt
 * und docs/adr/0006-telegram-webhook.md fuer die Begruendung.
 *
 * Benoetigte Worker-Umgebungsvariablen (als Secrets/Vars im Cloudflare-
 * Dashboard oder per `wrangler secret put` setzen):
 *   TELEGRAM_WEBHOOK_SECRET  — selbst gewaehlter zufaelliger String, muss mit
 *                              dem secret_token aus setWebhook uebereinstimmen
 *   GITHUB_TOKEN             — Personal Access Token mit Zugriff auf dieses
 *                              Repo (Actions: read/write)
 *   GITHUB_OWNER             — z.B. "Julian1612"
 *   GITHUB_REPO              — z.B. "Gravel-bot"
 */

export default {
  async fetch(request, env) {
    if (request.method !== "POST") {
      return new Response("OK", { status: 200 });
    }

    const secretHeader = request.headers.get("X-Telegram-Bot-Api-Secret-Token");
    if (!env.TELEGRAM_WEBHOOK_SECRET || secretHeader !== env.TELEGRAM_WEBHOOK_SECRET) {
      return new Response("Unauthorized", { status: 401 });
    }

    let update;
    try {
      update = await request.json();
    } catch (err) {
      return new Response("Bad Request: invalid JSON", { status: 400 });
    }

    const dispatchUrl = `https://api.github.com/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/dispatches`;
    const resp = await fetch(dispatchUrl, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        Accept: "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "gravel-bot-telegram-webhook",
      },
      body: JSON.stringify({
        event_type: "telegram_update",
        client_payload: update,
      }),
    });

    if (!resp.ok) {
      const body = await resp.text();
      console.error("GitHub repository_dispatch fehlgeschlagen", resp.status, body);
      return new Response("Dispatch failed", { status: 502 });
    }

    return new Response("OK", { status: 200 });
  },
};
