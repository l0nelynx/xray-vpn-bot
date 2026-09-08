/** Shared, in-memory support API for the two Vite mock frontends. */
import http from "node:http";
const stamp = (minutes = 0) =>
  new Date(Date.now() - minutes * 60000).toISOString();
let sequence = 100;
const assets = new Map();
const tickets = [
  {
    id: 1,
    subject: "Не подключается VPN · Android",
    category: "connection",
    status: "open",
    last_sender: "user",
    waiting_since: stamp(75),
    context: {
      platform: "Android",
      subscription: { id: 1, label: "Основная", product: "month" },
    },
    messages: [
      {
        id: 1,
        sender: "user",
        text: "После обновления приложения соединение не устанавливается. Пробовал Wi-Fi и мобильную сеть.",
        created_at: stamp(75),
        attachments: [],
      },
    ],
  },
  {
    id: 2,
    subject: "Оплата прошла, подписка не появилась",
    category: "payment",
    status: "in_progress",
    last_sender: "user",
    waiting_since: stamp(35),
    context: { payment: { id: "mock-payment-1", status: "paid", amount: 299 } },
    messages: [
      {
        id: 2,
        sender: "user",
        text: "Оплатил 299 рублей, но срок подписки не изменился. Посмотрите, пожалуйста.",
        created_at: stamp(35),
        attachments: [],
      },
      {
        id: 3,
        sender: "note",
        author: "admin",
        text: "Проверяем активацию после оплаты. Заметка видна только в dashboard.",
        created_at: stamp(30),
        attachments: [],
      },
    ],
  },
  {
    id: 3,
    subject: "Низкая скорость вечером",
    category: "speed",
    status: "waiting_user",
    last_sender: "admin",
    waiting_since: stamp(10),
    context: { platform: "Windows" },
    messages: [
      {
        id: 4,
        sender: "user",
        text: "Вечером видео долго загружается.",
        created_at: stamp(45),
        attachments: [],
      },
      {
        id: 5,
        sender: "admin",
        author: "admin",
        text: "Проверьте, пожалуйста, скорость через мобильную сеть. Если она выше, уточните вашего домашнего провайдера.",
        created_at: stamp(10),
        attachments: [],
      },
    ],
  },
  {
    id: 4,
    subject: "Подключение на iPhone",
    category: "connection",
    status: "closed",
    last_sender: "admin",
    waiting_since: stamp(120),
    closed_at: stamp(90),
    context: { platform: "iPhone / iPad" },
    messages: [
      {
        id: 6,
        sender: "user",
        text: "Помогите добавить подписку в приложение.",
        created_at: stamp(180),
        attachments: [],
      },
      {
        id: 7,
        sender: "admin",
        author: "admin",
        text: "Откройте «Подключиться» и нажмите «Добавить подписку». Рады, что всё заработало!",
        created_at: stamp(120),
        attachments: [],
      },
    ],
  },
].map((t) => ({
  ...t,
  user_id: 1,
  tg_id: 100001,
  username: "alice",
  created_at: t.messages[0].created_at,
  updated_at: t.messages.at(-1).created_at,
  assignee: null,
  admin_read_id: 0,
  user_read_id: 0,
}));
function serialize(t, admin) {
  const messages = t.messages.filter((m) => admin || m.sender !== "note");
  const publicMessages = t.messages.filter((m) => m.sender !== "note");
  const last = publicMessages.at(-1);
  return {
    ...t,
    messages,
    last_message_id: Math.max(0, ...publicMessages.map((m) => m.id)),
    last_message_preview: last?.text || "📷",
    unread: t.messages.some(
      (m) =>
        m.sender === (admin ? "user" : "admin") &&
        m.id > (admin ? t.admin_read_id : t.user_read_id),
    ),
    can_reopen:
      t.status === "closed" &&
      Date.now() - new Date(t.closed_at).getTime() < 7 * 86400000,
  };
}
async function body(req) {
  const chunks = [];
  let size = 0;
  for await (const c of req) {
    size += c.length;
    if (size > 16 * 1024 * 1024) throw new Error("File too large");
    chunks.push(c);
  }
  const b = Buffer.concat(chunks);
  if (req.headers["content-type"]?.includes("multipart/form-data"))
    return new Request("http://localhost", {
      method: "POST",
      headers: { "content-type": req.headers["content-type"] },
      body: b,
    }).formData();
  return b.length ? JSON.parse(b.toString()) : {};
}
async function attachments(form, t) {
  const files = form.getAll("images");
  if (files.length > 3) throw new Error("Up to 3 images");
  return Promise.all(
    files.map(async (file) => {
      if (file.size > 5 * 1024 * 1024) throw new Error("File too large");
      const id = ++sequence;
      assets.set(id, {
        buffer: Buffer.from(await file.arrayBuffer()),
        type: file.type,
        ticket: t.id,
      });
      return {
        id,
        filename: file.name,
        mime_type: file.type,
        size_bytes: file.size,
        url: `/support/tickets/${t.id}/attachments/${id}`,
      };
    }),
  );
}
const server = http.createServer(async (req, res) => {
  const json = (value, status = 200) => {
    res.writeHead(status, {
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
    });
    res.end(JSON.stringify(value));
  };
  try {
    const url = new URL(req.url, "http://localhost");
    const admin = url.pathname.includes("/dashboard/");
    const path = url.pathname.replace(/^.*\/api\/support/, "");
    if (url.pathname === "/health")
      return json({ ok: true, tickets: tickets.length });
    if (!url.pathname.includes("/api/support"))
      return json({ detail: "Not found" }, 404);
    if (path === "/context")
      return json({
        subscriptions: [
          { id: 1, label: "Основная" },
          { id: 2, label: "Семейная" },
        ],
        payments: [{ id: "mock-payment-1", label: "299 RUB · сегодня" }],
      });
    if (path === "/tickets" && req.method === "GET") {
      let selected = tickets.map((t) => serialize(t, admin));
      const counts = {
        needs_reply: selected.filter((t) =>
          ["open", "in_progress"].includes(t.status),
        ).length,
        waiting_user: selected.filter((t) => t.status === "waiting_user")
          .length,
        active: selected.filter((t) => t.status !== "closed").length,
        closed: selected.filter((t) => t.status === "closed").length,
      };
      if (!admin)
        return json(
          selected.sort(
            (a, b) =>
              Number(a.status === "closed") - Number(b.status === "closed") ||
              b.updated_at.localeCompare(a.updated_at),
          ),
        );
      const q = url.searchParams.get("queue");
      if (q === "needs_reply")
        selected = selected.filter((t) =>
          ["open", "in_progress"].includes(t.status),
        );
      else if (q === "active")
        selected = selected.filter((t) => t.status !== "closed");
      else if (q && q !== "all")
        selected = selected.filter((t) => t.status === q);
      const search = (url.searchParams.get("search") || "").toLowerCase();
      selected = selected.filter((t) =>
        `${t.subject} #${t.id} ${t.username} ${t.tg_id}`
          .toLowerCase()
          .includes(search),
      );
      selected.sort((a, b) =>
        q === "needs_reply"
          ? a.waiting_since.localeCompare(b.waiting_since)
          : String(
              b[url.searchParams.get("sort") || "updated_at"],
            ).localeCompare(
              String(a[url.searchParams.get("sort") || "updated_at"]),
            ),
      );
      const page = Number(url.searchParams.get("page") || 1);
      return json({
        items: selected.slice((page - 1) * 20, page * 20),
        total: selected.length,
        counts,
        page,
        per_page: 20,
      });
    }
    if (path === "/tickets/create" && req.method === "POST") {
      if (tickets.filter((t) => t.status !== "closed").length >= 5)
        return json(
          {
            detail: "У вас уже 5 активных обращений. Продолжите существующее.",
          },
          429,
        );
      const form = await body(req);
      const now = stamp();
      const t = {
        id: ++sequence,
        user_id: 1,
        tg_id: 100001,
        username: "alice",
        subject: String(form.get("subject")),
        category: String(form.get("category")),
        status: "open",
        last_sender: "user",
        waiting_since: now,
        created_at: now,
        updated_at: now,
        context: {
          platform: String(form.get("platform") || "—"),
          ...(form.get("subscription_id")
            ? {
                subscription: {
                  id: Number(form.get("subscription_id")),
                  label: "Основная",
                },
              }
            : {}),
          ...(form.get("payment_id")
            ? {
                payment: {
                  id: form.get("payment_id"),
                  amount: 299,
                  status: "paid",
                },
              }
            : {}),
        },
        messages: [],
        admin_read_id: 0,
        user_read_id: 0,
        assignee: null,
      };
      t.messages.push({
        id: ++sequence,
        sender: "user",
        text: String(form.get("message")),
        created_at: now,
        attachments: await attachments(form, t),
      });
      tickets.unshift(t);
      return json(serialize(t, false), 201);
    }
    const match = path.match(/^\/tickets\/(\d+)(.*)$/);
    if (!match) return json({ detail: "Not found" }, 404);
    const t = tickets.find((t) => t.id === Number(match[1]));
    if (!t) return json({ detail: "Not found" }, 404);
    const action = match[2];
    if (!action && req.method === "GET") return json(serialize(t, admin));
    if (action.startsWith("/attachments/")) {
      const id = Number(action.split("/").at(-1));
      const asset = assets.get(id);
      if (
        !asset ||
        asset.ticket !== t.id ||
        (!admin &&
          t.messages.some(
            (m) =>
              m.sender === "note" && m.attachments.some((a) => a.id === id),
          ))
      )
        return json({ detail: "Not found" }, 404);
      res.writeHead(200, { "Content-Type": asset.type });
      return res.end(asset.buffer);
    }
    if (action === "/read") {
      const b = await body(req);
      const k = admin ? "admin_read_id" : "user_read_id";
      t[k] = Math.max(t[k], Number(b.message_id));
      return json({ ok: true });
    }
    if (action === "/claim") {
      t.assignee = req.method === "DELETE" ? null : "admin";
      return json({ ok: true });
    }
    if (!action && req.method === "PATCH") {
      const b = await body(req);
      t.status = b.status;
      t.closed_at = b.status === "closed" ? stamp() : null;
      t.updated_at = stamp();
      return json({ ok: true });
    }
    if (action === "/outcome") {
      const b = await body(req);
      if (
        b.action === "reopen" &&
        !serialize(t, false).can_reopen &&
        t.status === "closed"
      )
        return json({ detail: "Reopen period expired" }, 409);
      t.status = b.action === "resolved" ? "closed" : "open";
      t.closed_at = b.action === "resolved" ? stamp() : null;
      t.waiting_since = stamp();
      return json({ ok: true });
    }
    if (action.startsWith("/messages/") && req.method === "DELETE") {
      const id = Number(action.split("/").at(-1));
      t.messages = t.messages.filter(
        (m) => m.id !== id || m.sender !== "admin",
      );
      return json({ ok: true });
    }
    if (
      (action === "/reply" || action === "/messages") &&
      req.method === "POST"
    ) {
      const form = await body(req);
      const internal = admin && form.get("internal") === "true";
      if (t.status === "closed" && !internal)
        return json({ detail: "Ticket closed" }, 409);
      const sender = internal ? "note" : admin ? "admin" : "user";
      const now = stamp();
      const msg = {
        id: ++sequence,
        sender,
        author: admin ? "admin" : null,
        text: String(form.get("text") || ""),
        created_at: now,
        attachments: await attachments(form, t),
      };
      t.messages.push(msg);
      if (!internal) {
        if (t.last_sender !== sender) t.waiting_since = now;
        t.last_sender = sender;
        t.status = admin
          ? form.get("close") === "true"
            ? "closed"
            : "waiting_user"
          : "open";
        t.closed_at = t.status === "closed" ? now : null;
        t.updated_at = now;
      }
      return json(admin ? { ok: true } : msg, 201);
    }
    return json({ detail: "Unsupported action" }, 400);
  } catch (e) {
    json({ detail: e.message }, 400);
  }
});
server.listen(8790, "127.0.0.1", () =>
  console.log("Shared support mock API: http://127.0.0.1:8790"),
);
