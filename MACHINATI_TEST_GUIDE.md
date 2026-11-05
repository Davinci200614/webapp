# MACHINATI integration: feature check and test guide

Source comparison on 2026-11-05. Original catalogue/cooperative/operations documents and the original React priority
dashboard are now used. Source CSS hashes are preserved; browser visual verification is pending. Webapp has its own database: old MACHINATI records are not imported automatically.

| Original capability | Webapp | Result |
|---|---|---|
| WhatsApp text/voice machinery requests | WhatsApp → `/requests` | Present, with follow-up, correction and explicit confirmation |
| Catalogue/filtering | `/` | Live inventory, hourly estimate and WhatsApp handoff |
| Inventory creation/editing | `/machines` | Present; admin write access |
| Priority score and reasons | `/requests` | Present: urgency, verification, age, fit and declared date window |
| Type/locality/date/owner-use matching | `/requests` | Present, with alias normalization |
| Human urgency verification | `/requests` | Present; reviewer name required |
| Approve/reject/complete | `/requests` | Present, with enforced lifecycle |
| Cooperative overview/planning | `/cooperative` | Inventory overview and approved requests by desired date |
| Operations summaries/trends/filtering | `/operations` | Derived from stored requests |
| Legal pages | `/privacy`, `/terms`, `/data-deletion` | Present; operator-specific placeholders remain |
| Original IoT and verification panels | No live counterpart | Original demonstration panels had no real backend service |
| Cooperative introduction | Catalogue button | WhatsApp introduction, not automatic registration/verification |

Neither MVP provides guaranteed booking, automatic machine allocation, payment,
live GPS, travel feasibility or conflict-free scheduling. Approval does not book
or reserve a machine. Private webapp pages now require login.

## Start and prepare

If no administrator exists, set `AUTH_BOOTSTRAP_EMAIL` and
`AUTH_BOOTSTRAP_PASSWORD` (12+ characters) in `backend/.env`, then restart:

```bash
./webapp/start.sh --restart
```

Open http://localhost:8000/machines and sign in. Development mode uses website
port 5173. Keep the working Meta/AI configuration; use the printed callback URL
in Meta if it changed. Set `WHATSAPP_CONTACT_NUMBER` for website handoff links.

## Controlled manual test

1. In `/machines`, create `TEST - Tractor Meknes`, type `tractor`, location
   `Meknes`, hourly rate `200`, available enabled, owner-use reservation disabled.
   Leave date limits empty or choose a window containing your test request date.
   Save and refresh; confirm it appears in the inventory and public catalogue.
2. On `/`, filter by type/location. Open the machine request form and choose
   three hours in the request dialog: the estimate should be 600 MAD excluding transport. Continue to
   WhatsApp. This prepares a message; sending and confirmation are still necessary.
3. Finish/cancel any current employment draft. Send a machinery request:

   > بغيت تراكتور للحرث، عندي جوج هكتارات فمكناس، نهار 15 نونبر 2026

   Substitute a future date inside the availability window. Answer follow-ups.
   Before confirmation, send `لا، المساحة ثلاثة هكتارات`. Verify the preview
   changes area to 3 and preserves the other fields. A new saved request should
   not appear in `/requests` until explicit confirmation. Confirm, refresh and
   check one new `pending_review` request. Repeat separately by voice.
4. Check candidate machines in `/requests`. Your test tractor should qualify
   locally. Edit it, refresh requests, and check each scenario separately:

   | Inventory change | Expected result |
   |---|---|
   | Mark unavailable | Test tractor excluded |
   | Mark reserved for owner use | Test tractor excluded |
   | Date window entirely after requested date | Test tractor excluded |
   | Move to Fes, restore dates/availability | Transport review if no eligible local alternative |

   Other machines may still match. Check your test machine's presence instead
   of assuming the whole candidate list becomes empty. Restore each field after testing.
5. Create a separate request declaring urgency and a reason, for example:

   > محتاج حصادة للحصاد فمكناس، عندي 12 هكتار نهار 15 نونبر 2026، مستعجل حيت خاصني نكمل الحصاد قبل الشتا

   Replace the date appropriately. Verify urgency/reason in the preview and
   confirm. In `/requests`, enter a name in `Vérifié par`, then click
   `Valider l'urgence` before approval. Reviewer should persist and score increase.
   Read score reasons: machine fit and age also influence queue position.
6. Approve a pending test request. It should appear under approved requests in
   `/cooperative`; `/operations` should reflect the status change. Mark it completed
   from `/requests`: it becomes `Terminée` and leaves the cooperative approved list.
   Reject a different pending request. Completed/rejected requests cannot be reopened
   through the supported status lifecycle.
7. Log out: private pages should require login while catalogue remains public.
   A regular operator can review requests but cannot create/edit inventory.
   Restart and confirm saved test records/statuses persist.

`/inspect` can show stored transcripts/drafts/replies for an administrator when
`INSPECTOR_ENABLED=true`. Check the transcript separately from the extracted request.

## Automated verification

From the workspace root:

```bash
(cd webapp/backend && .venv/bin/python -m scripts.run_tests)
(cd webapp/frontend && npm run build && npm run test:render)
```

Backend tests use temporary databases and mocked external services. Frontend render
checks do not exercise browser interaction. A live WhatsApp test is still necessary.
No demo seeding is required. Optional `scripts.seed_demo` adds fictional inventory,
priority requests and employment records to the configured database.
