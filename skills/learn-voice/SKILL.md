---
name: learn-voice
description: Learn how the business owner writes to customers (languages they mix, tone, length, greetings, emoji, favourite words) from their own past replies, and save a short voice.md style guide after the owner confirms it. Use when the owner says "learn how I write", "learn my voice", "update my voice", or "my drafts don't sound like me".
allowed-tools: Bash(python3 -I ${CLAUDE_PLUGIN_ROOT}/scripts/gw_learn.py *)
---

# Learn the owner's voice

You help the owner of a small business teach the draft writer how they write. The result is one file, `voice.md`, in the owner's ghostwriter data folder. The draft writer reads it for every draft, so keep it short.

Talk to the owner in plain, friendly language, and say "you". The owner is not a developer. The owner may write in any language: reply in the language they use.

## Rules that always apply

- The owner confirms the file before you save it. Show it, apply the corrections, then write.
- Never overwrite the owner's manual edits. On a re-run, show what would change and keep the edits unless the owner agrees to replace them.
- Example replies come from the owner's own replies only. Never copy customer text into the file. Never put customer names, phone numbers, street addresses or order numbers in it. Pick replies that have none, or leave those parts out.
- Do not read the chat history yourself with other tools. Use the script. It does the scanning, so you only see statistics and a small sample.
- Keep the file under 12 000 characters.

## Step 1: Set up and choose the history

Run:

```
python3 -I ${CLAUDE_PLUGIN_ROOT}/scripts/gw_learn.py init
```

- `init` prints the data folder and the file paths. The default folder is `~/.ghostwriter`. Tell the owner which folder it is.
- `init` never overwrites. An existing `voice.md` stays as it is.
- If it prints a note about an older folder, tell the owner. Offer to copy the files from there into the new folder. Copy only after a yes, and never over a file that already has content.
- If the owner also runs automatic drafts with the whatsapp-mcp bridge, the bridge must use the same folder. If it has `GHOSTWRITER_HOME` set, the same value must be set here. If the two differ, stop and help fix that first.

Then ask the owner where the history comes from, unless it is already clear:

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

## Step 2: Read the owner's writing

1. Run `python3 -I ${CLAUDE_PLUGIN_ROOT}/scripts/gw_learn.py <source options> voice-sample`. Add `--n 100` for a larger sample if the owner writes in several styles. If it says that no messages were found, check the name with `names`, and the date order.
2. Read the Stats section and the sample replies. The sample leaves out replies the owner sends often, because those belong in templates.
3. Read the current `voice.md`. If it only has the empty headings, it is a first run.

## Step 3: Ask one question

Ask which language the owner wants the draft notes in. The notes are the short line that comes with each draft, for example "check the date before you send". Suggest the language the owner writes most. Put the answer in the `Notes language:` line.

## Step 4: Write the guide

Use exactly this layout. Keep the first two lines as they are. Write each section as 1 to 4 short lines or bullets, based on the statistics and the sample. Write in third person: "the owner", "they".

```
# Voice
Notes language: <language>

## Languages and mixing
## Tone
## Length
## Greetings and sign-offs
## Emoji and punctuation
## Words and phrases the owner uses
## Things the owner avoids
## Example replies
- "<one of the owner's real replies>"
```

- Languages and mixing: which languages the owner uses and how they mix them, for example Indonesian with English product words, Spanish and English, or Hindi written in Latin letters.
- Tone: warm, formal, joking, brisk. Say how the owner addresses customers, for example by first name, "kak", "sir" and "ma'am", "señora", or no form of address.
- Length: the usual length in sentences or words, from the median in the Stats.
- Greetings and sign-offs: how the owner opens and closes, from the top first and last words and the sample.
- Emoji and punctuation: which emoji the owner uses and how often, whether they use "!" and "?" and "..." and so on.
- Words and phrases the owner uses: words from the top-words list and the sample that carry their style.
- Things the owner avoids: only what the data shows, such as "no emoji in price messages". Do not guess. If there is nothing clear, write "Nothing clear yet."
- Example replies: 6 to 10 short replies copied from the sample, with the exact wording and emoji the owner used. One reply per line, in quotes. Choose replies that show different situations. Remove or avoid anything that names a customer or contains a number that belongs to a customer.

## Step 5: Confirm and save

1. Show the owner the whole guide. Say which replies you used as examples, and ask the owner to correct anything that does not sound like them.
2. Apply the corrections.
3. If `voice.md` already has content from before, show what changes section by section. Keep every line the owner edited unless they say to replace it. Save only the sections the owner approves.
4. Write `voice.md` only after a clear yes. Tell the owner the folder and that they can open the file and edit it any time.
5. Tell the owner to run this skill again after a few months, or when drafts stop sounding like them.
