---
name: learn-templates
description: Learn the replies the business owner sends again and again (directions, booking steps, payment details) and the business facts in them (address, hours, prices), then save them as templates.md and facts.md after the owner confirms. Use when the owner says "learn my templates", "find my repeated replies", "add this as my parking template", "change my directions template", or "update my facts".
allowed-tools: Bash(python3 -I ${CLAUDE_PLUGIN_ROOT}/scripts/gw_learn.py *)
---

# Learn templates and facts

You help the owner of a small business teach the draft writer their repeated replies. The result is two files in the owner's ghostwriter data folder: `templates.md` and `facts.md`. The draft writer reads both for every draft, so keep them short and accurate.

Talk to the owner in plain, friendly language, and say "you". The owner is not a developer. The owner may write in any language: reply in the language they use.

## Rules that always apply

- The owner confirms every change before you save it. Show what will change, wait for a clear yes, then write.
- Never overwrite or delete anything the owner wrote or edited. Add new sections and change only the ones the owner agrees to change.
- Never put customer names, customer phone numbers or other customer details in any file. Customer messages in the script output are context only.
- Payment details (bank, account number, e-wallet) and the business phone number go into `facts.md` only if the owner says yes to that exact item.
- Do not read the chat history yourself with other tools. Use the script. It does the scanning, so you only see a short summary.
- Keep each file under 12 000 characters. If a change would go over, say so and ask what to trim.

## Step 1: Set up

Run:

```
python3 -I ${CLAUDE_PLUGIN_ROOT}/scripts/gw_learn.py init
```

- `init` prints the data folder and the three file paths. The default folder is `~/.ghostwriter`. Tell the owner which folder it is.
- `init` never overwrites. Existing files stay as they are.
- If it prints a note about an older folder, tell the owner. Offer to copy the files from there into the new folder. Copy only after a yes, and never over a file that already has content.
- If the owner also runs automatic drafts with the whatsapp-mcp bridge, the bridge must use the same folder. If it has `GHOSTWRITER_HOME` set, the same value must be set here. If the two differ, stop and help fix that first.

Flows B and C need nothing more. Flow A needs the chat history: do step 2 first.

## Step 2: Choose where the history comes from

Ask the owner, unless it is already clear:

- **With the whatsapp-mcp bridge.** If `WHATSAPP_STORE_DIR` is set, add nothing. If it is not set, ask for the path of the bridge's `store` folder (the folder with `messages.db`; usually `whatsapp-bridge/store` inside the whatsapp-mcp folder). Add `--store-dir <that folder>` before the command in every script call below.
- **Without the bridge, from exported chats.** Tell the owner:
  1. Open a chat with a typical customer in WhatsApp. On iPhone: tap the contact name at the top, scroll down, tap **Export Chat**, choose **Without Media**. On Android: tap **⋮**, then **More**, then **Export chat**, then **Without media**.
  2. Send the file to your computer (for example by email, AirDrop or a cloud drive). Put every exported file in one new folder.
  3. Export 3 to 10 chats with typical customers. One-to-one chats only: group chats are skipped. The files hold customer messages, so keep the folder private and delete it when you are done.

  When the folder is ready, ask for its path. Put the path in quotes if it has spaces. Run:

  ```
  python3 -I ${CLAUDE_PLUGIN_ROOT}/scripts/gw_learn.py --export <folder> names
  ```

  It lists every sender name with its message count. The owner's name is usually the one that appears in every file. Ask the owner to confirm which name is theirs. Then add `--export <folder> --me "<name>"` before the command in every script call below. If the dates look wrong (day and month swapped), add `--date-order mdy` or `--date-order dmy`.

The scripts only read the history. They never change it.

## Flow A: Learn from the owner's history

Use this when the owner asks you to learn or find their templates.

1. Run `python3 -I ${CLAUDE_PLUGIN_ROOT}/scripts/gw_learn.py <source options> find-templates`. Add `--min-count 2` only if the result is thin and the owner agrees. If it says that no messages were found, check the name with `names`, and the date order.
2. Read `templates.md` and `facts.md` (paths from `init`).
3. Choose at most 15 templates. Prefer replies used often, in many chats, and recently. For each one write:
   - a short name in the owner's language, for example "Directions to the shop", "Cara pesan", "Horario";
   - `Use when:` one line that says what the customer asked;
   - the text of the owner's most recent version, with `{placeholders}` for the parts that change: `{date}`, `{time}`, `{name}`, `{price}`, `{quantity}`, `{item}`. Keep the owner's wording, emoji and line breaks.
4. Look for business facts that appear across the templates: address, opening hours, prices, delivery or return policy, how to book. Write each as `- Label: value`. Mark payment details and phone numbers as "needs your yes".
5. Show the owner one proposal. For each template say whether it is new, the same as one they already have, or a change to one they have. For a change, show the old and new text. Show the facts as a list. Ask what to drop, rename or fix.
6. After the owner approves, save:
   - `templates.md`: keep the `# Templates` heading and all existing sections. Add the new ones as `## <Name>`, then `Use when: ...`, then the text. Change an existing section only if the owner approved that change.
   - `facts.md`: keep the `# Facts` heading and all existing lines. Add new lines as `- Label: value`. If a label already exists with another value, ask which one is right.
7. Tell the owner what you saved and the number of templates and facts now in each file. Suggest the `learn-voice` skill if the owner has not run it yet.

## Flow B: Add or change one template

Use this when the owner describes a template in their own words, for example "add this as my parking template: ...".

1. Run `init` as in step 1. Do not run `find-templates`.
2. Read `templates.md`. If a template with that name or purpose exists, show it and ask whether to replace it or add a new one.
3. Write the template from the owner's words. Add `{placeholders}` where the text changes from one customer to the next. Show it to the owner.
4. After the owner approves, save it with the same rules as step 6 above.

## Flow C: Update facts

Use this when the owner gives you a new fact or a changed one, for example new opening hours.

1. Run `init`, then read `facts.md`.
2. Show the lines that would be added or changed, old value next to new value.
3. After the owner approves, save. Leave all other lines as they are.
