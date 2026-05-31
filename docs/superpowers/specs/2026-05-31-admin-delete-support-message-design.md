# Admin Delete Support Message — Design

**Date:** 2026-05-31
**Status:** Draft, awaiting review

## Problem

The dashboard's support panel lets admins reply to user tickets but
cannot remove a reply once sent. If an admin replies with the wrong
text (typo, wrong ticket, sensitive info) there is no recovery path
short of editing the database directly.

## Goal

Give the dashboard admin a way to delete their own support replies.

## Scope

In:
- New `DELETE` endpoint in `dashboard/backend/routers/support.py`.
- New repo helper in `packages/common_db/common_db/repo/support.py`.
- Unit tests for the helper in
  `packages/common_db/tests/test_repo_support.py`.

Out:
- Soft delete / tombstones. Hard delete only.
- Deleting user-authored messages. Only `sender='admin'` rows are
  deletable.
- Any change to `miniapp/backend/routers/support.py`. The user-facing
  GET reads through `list_messages_for_ticket`, so deleted rows simply
  stop appearing on the next fetch.
- Telegram notification to the user about the deletion. Silent
  operation by design.
- New auth roles. The existing `get_current_user` dashboard auth
  already gates admin-only endpoints.

## Design

### 1. New repo helper

`packages/common_db/common_db/repo/support.py`:

```python
async def delete_admin_message(
    session: AsyncSession, ticket_id: int, message_id: int
) -> bool:
    """Delete an admin-authored message from a ticket.

    Returns True if a row was deleted, False otherwise. False covers:
    message_id does not exist, belongs to a different ticket, or has
    sender != 'admin'. Caller commits.
    """
```

Implementation: single `sqlalchemy.delete(SupportMessage)` with
`WHERE id = :message_id AND ticket_id = :ticket_id AND sender =
'admin'`. Use `await session.execute(stmt)` and return
`result.rowcount > 0`.

Add `delete_admin_message` to the module's `__all__`.

### 2. New dashboard endpoint

`dashboard/backend/routers/support.py`:

```
DELETE /api/support/tickets/{ticket_id}/messages/{message_id}
```

Handler logic (sequential):

1. `get_current_user` dependency — same auth as `reply_ticket` and
   `update_status`.
2. Open `async_session()`.
3. `ticket = await _repo_support.get_ticket_by_id(session,
   ticket_id)`; raise `HTTPException(404, "ticket not found")` if
   None.
4. `deleted = await _repo_support.delete_admin_message(session,
   ticket_id, message_id)`.
5. If not `deleted`: raise `HTTPException(404, "message not found")`.
6. `ticket.updated_at = _now_iso()`.
7. `await session.commit()`.
8. Return `{"ok": True}`.

No Telegram notification. The miniapp will reflect the deletion the
next time the user opens the ticket.

### 3. Authorization model

- Endpoint requires the dashboard admin session via
  `get_current_user`. This matches every other write endpoint in the
  same router (`reply_ticket`, `update_status`).
- The repo helper enforces `sender = 'admin'` at the SQL level. A
  request that names a user-authored `message_id` returns 404; the
  row is never touched.
- The endpoint requires both `ticket_id` and `message_id` in the URL,
  and the helper's WHERE clause checks both. An admin who guesses a
  `message_id` but pairs it with the wrong `ticket_id` gets 404 — the
  message stays put.

### 4. Error responses

| Condition                                      | Status | Body                          |
| ---------------------------------------------- | ------ | ----------------------------- |
| Auth missing/invalid                           | 401    | from `get_current_user`       |
| Ticket id does not exist                       | 404    | `{"detail": "ticket not found"}`  |
| Message id does not exist                      | 404    | `{"detail": "message not found"}` |
| Message belongs to a different ticket          | 404    | `{"detail": "message not found"}` |
| Message exists but `sender = 'user'`           | 404    | `{"detail": "message not found"}` |
| Success                                        | 200    | `{"ok": true}`                |

A uniform 404 for the four "cannot delete" cases keeps the handler
simple and avoids leaking which message ids exist.

## Test plan

New cases in `packages/common_db/tests/test_repo_support.py` covering
`delete_admin_message`:

1. Seed a ticket with one user message and one admin message. Delete
   the admin message → helper returns `True`; querying the ticket's
   messages returns only the user message.
2. Same seed. Call helper with the user message's id → returns
   `False`; both messages still present.
3. Seed two tickets, each with an admin message. Call helper with
   ticket_A's id and ticket_B's admin-message id → returns `False`;
   ticket_B's message untouched.
4. Helper with a `message_id` that does not exist → returns `False`.

No new dashboard-level tests are required: the endpoint is a thin
wrapper around the helper, and existing helpers
(`get_ticket_by_id`) are already covered.

## Migration

None. No schema change.

## Rollout

Single change set. Deploy dashboard backend; the new endpoint is
inert until called.

## Open questions

None.
