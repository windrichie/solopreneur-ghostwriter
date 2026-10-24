# Solopreneur Ghostwriter

Ghostwriter is a Claude Code plugin that drafts replies to your customers in your own voice. It learns from your past WhatsApp chats: how you write, the replies you send again and again, and the facts about your business. Then you paste a customer's message into Claude Code and get a draft you can send as it is or fix in a few seconds. Ghostwriter never sends anything to a customer.

It has three skills:

- `learn-voice` reads your past replies and writes a short style guide, `voice.md`.
- `learn-templates` finds the replies you repeat (directions, booking steps, prices) and saves them as `templates.md`, with the facts in them as `facts.md`.
- `draft-reply` writes a draft from those three files.

If you also run the [whatsapp-mcp](https://github.com/windrichie/whatsapp-mcp) bridge, Ghostwriter can write drafts for you automatically. See [Automatic drafts with whatsapp-mcp](#automatic-drafts-with-whatsapp-mcp). You do not need the bridge to use the plugin.

## Install

You need [Claude Code](https://claude.com/claude-code) and Python 3.9 or newer. For the one-step install, use Claude Code 2.1.275 or newer. Run this in Claude Code:

```
/plugin install solopreneur-ghostwriter --marketplace windrichie/solopreneur-ghostwriter
```

Or do it in two steps:

```
/plugin marketplace add windrichie/solopreneur-ghostwriter
/plugin install solopreneur-ghostwriter@solopreneur-ghostwriter
```

To work on the plugin itself, start Claude Code from a local copy:

```bash
claude --plugin-dir /path/to/solopreneur-ghostwriter
```

The skills are then named `/solopreneur-ghostwriter:learn-voice` and so on. You can also type what you want, for example "learn my voice" or "draft a reply to this".

## Use it on its own

1. **Export a few chats from WhatsApp.** Open a chat with a typical customer. On iPhone, tap the contact name at the top, scroll down, tap **Export Chat**, then **Without Media**. On Android, tap **⋮**, then **More**, then **Export chat**, then **Without media**. Send the file to your computer and put it in a new folder. Do this for 3 to 10 chats. Use one-to-one chats: group chats are skipped. Both the `.txt` file and the `.zip` file that WhatsApp makes work.
2. **Run the two learning skills**, one after the other:

   ```
   /solopreneur-ghostwriter:learn-voice
   /solopreneur-ghostwriter:learn-templates
   ```

   Each skill asks for the folder of exports and shows you the sender names it found, so you can say which one is you. Each shows what it plans to save. Nothing is saved until you say yes.
3. **Paste a customer message and ask for a draft.** For example: "Draft a reply to this: *hi, are you open on Sunday?*". Claude writes the reply and a short note, such as "check the delivery date". You copy the reply into WhatsApp and send it yourself.

Run both learning skills again after a few months, or when drafts stop sounding like you. Delete the exported files when you are done: they hold your customers' messages.

The learning skills read at most the newest 20 000 of your messages and work from a short summary, so they stay cheap.

## Automatic drafts with whatsapp-mcp

[whatsapp-mcp](https://github.com/windrichie/whatsapp-mcp) is a WhatsApp bridge that runs on your computer. It saves your messages in a local database, and it can run a command after a customer writes and then goes quiet. Ghostwriter's runner, `bin/draft`, is that command. It writes a draft and the bridge sends it to your own "Message yourself" chat. You read it, fix anything that is wrong, then copy it into the customer's chat and send it yourself.

Step-by-step setup on a Mac: [docs/automatic-drafts-macos.md](docs/automatic-drafts-macos.md)

With the bridge you can also teach Ghostwriter from its database instead of exports. When a learning skill asks where your history comes from, choose the bridge and give it the path of the bridge's `store` folder, or set `WHATSAPP_STORE_DIR` to that path before you start Claude Code.

### Turn on drafts in the bridge

Set these in the environment where the bridge starts, then restart the bridge:

| Variable | Value |
|---|---|
| `WHATSAPP_DRAFTS` | `1` to turn drafts on. |
| `WHATSAPP_DRAFT_COMMAND` | The absolute path of the runner: `<path of this repo>/bin/draft`. The file must be executable. |
| `WHATSAPP_DRAFT_DELAY_SECONDS` | How long the bridge waits after the last customer message before it drafts. Default 90. Allowed range: 5 to 3600 seconds. |
| `WHATSAPP_DRAFTS_PER_HOUR` | The most drafts in one hour. Default 30. |
| `WHATSAPP_DRAFT_CHATS` | A comma-separated list of chats that get drafts. If you leave it empty, every one-to-one chat gets drafts. Start with one chat that you use for tests. |
| `WHATSAPP_DRAFT_SKIP_CHATS` | Chats that never get drafts, for example family and friends. |
| `WHATSAPP_READ_ONLY` | Keep this at `1`. |

For the chat lists, write a phone number with country code and no `+`, for example `6591234567`, or a `...@lid` address. Group chats are not allowed. The bridge will not start if an entry is not valid.

### Settings for the runner

These are optional. Set them in the same place as the bridge variables.

| Variable | What it does |
|---|---|
| `GHOSTWRITER_MODEL` | The Claude model used for drafts. Default `sonnet`. |
| `CLAUDE_BIN` | The path of the `claude` program. Set it if the bridge cannot find `claude`. |
| `GHOSTWRITER_PYTHON` | The path of a Python 3.9 or newer. Set it if the bridge starts from `launchd` or another place with a short `PATH`. |
| `GHOSTWRITER_HOME` | The folder for your voice, templates, facts and draft log. Default `~/.ghostwriter`. |
| `GHOSTWRITER_CLAUDE_TIMEOUT` | How many seconds the runner waits for the model. Default 150. |

### Ask for a draft by hand

You can ask the bridge for a draft for one chat at any time. The bridge writes a new token to `store/api_token` each time it starts. Replace the chat address with the customer's:

```bash
curl -s -X POST http://127.0.0.1:8080/api/draft \
  -H "Authorization: Bearer $(cat /path/to/whatsapp-mcp/whatsapp-bridge/store/api_token)" \
  -H "Content-Type: application/json" \
  -d '{"chat_jid": "6591234567@s.whatsapp.net"}'
```

The answer is "draft sent to your own chat" or "no reply needed". It returns an error if drafts are not turned on, if the chat is your own chat, or if you reached the hourly limit.

### What the bridge adds to the safety model

- The bridge stays read-only for the AI. Keep `WHATSAPP_READ_ONLY=1`. It has one narrow exception: it can send a draft to your own chat and nowhere else. It checks this itself, so nothing the AI writes can change who receives a message.
- The runner is the only part that calls a model, and the model it calls has no tools.
- The bridge is an unofficial WhatsApp client. WhatsApp can ban accounts that use unofficial clients, and this setup does not remove that risk. It keeps the footprint small: the bridge reads messages and sends a few messages to yourself. It does not send to customers. Read the bridge's own security notes before you rely on it.

## How it stays safe

- Ghostwriter never sends a message to a customer. You read each draft and send it yourself.
- When you use the plugin on its own, drafts are written inside your normal Claude Code session. Nothing is sent to WhatsApp.
- The runner for automatic drafts calls Claude with no tools. It cannot read files, browse, or send.
- Customer messages are treated as untrusted text. A customer who writes "ignore your rules" gets no special treatment.
- Pasted text never goes into a shell command. The `draft-reply` skill reads your three files with a command that takes no arguments, and you paste the customer's message into the chat.
- Your data files are private. The data folder is readable by your user only (mode 0700) and each file in it too (0600).
- The learning scripts only read your chat exports and the bridge database. They never change them.
- Names and phone numbers of your customers are not saved in `voice.md`, `templates.md` or `facts.md`.

## Files and privacy

Everything lives in one folder, `~/.ghostwriter`. To use another folder, set `GHOSTWRITER_HOME`. Both modes use the same folder.

| File | What it holds |
|---|---|
| `voice.md` | How you write, with a few of your own replies as examples. |
| `templates.md` | Replies you send again and again, with `{placeholders}` for the parts that change. |
| `facts.md` | Facts drafts can use: address, hours, prices, policies. Bank details are in it only if you said yes. |
| `drafts.jsonl` | A log with one line for each automatic draft: the draft, the customer's chat address, and the cost. |

You can open and edit the three Markdown files in any text editor. The skills keep your edits when you run them again. The runner reads at most 12 000 characters from each file, so keep them short.

**Moving from an older version.** Older versions kept these files in a `ghostwriter` folder inside the bridge's `store` folder. The default is now `~/.ghostwriter`. Copy the files over, or set `GHOSTWRITER_HOME` to the old folder to keep using it. The learning skills, `gw_draft.py files` and `bin/draft` print a reminder while your files remain in the old place and the new folder has none. `bin/draft` prints it on stderr only, so drafts still work, but without your voice, templates and facts until you move the files.

**Two WhatsApp accounts on one computer** need one data folder each. Give each its own `GHOSTWRITER_HOME`.

Everything stays on your computer, with these exceptions. When you use the plugin on its own, the files and the messages you paste go to Claude as part of your Claude Code session. For each automatic draft, the runner sends the file contents and the recent messages of that chat to Claude. Do not put anything in these files that you would not want Claude to see.

## Cost

- Automatic drafts make one model call for each burst of customer messages, after the delay. There are no calls when the shop is quiet. The call is billed to whichever Claude account or API key `claude` uses on that computer. `drafts.jsonl` records the cost that Claude reports for each draft. If the plugin is for a business, set `claude` up with the business's own Claude account or API key.
- Drafting by hand uses your normal Claude Code session, so it counts toward that session's usage.
- The two learning skills work from a short summary of your history, so they cost little.

## Troubleshooting

**"No messages found" when learning from exports.**
1. Run the `names` command that the skill showed you. Check that your name is in the list, and pass it exactly as `--me "<name>"`. Capital letters do not matter.
2. Check the dates. If WhatsApp wrote `03/04/2026`, the script cannot tell whether that is 3 April or 4 March. It looks for a day above 12 in the file. If every date is 12 or below, it assumes day first. Add `--date-order mdy` if your dates start with the month.
3. Use exports made with **Without Media**. A group chat is skipped with a warning. Placeholders for photos and other media in a language other than English may be counted as messages: this is harmless, but it shows up as text in the summary.

**The skill cannot tell which name is yours.** Run `names`, then pass `--me "<name>"`. This happens when you give it a single file: both names are then in every file.

**Drafts do not sound like you.** Run `/solopreneur-ghostwriter:learn-voice` again, with more chats. Check `voice.md` and fix anything that is wrong.

**A draft uses the wrong price or time.** Open `facts.md` and `templates.md` and correct the lines. Run `/solopreneur-ghostwriter:learn-templates` again to add what is missing.

**No automatic drafts arrive.**
1. Check that `WHATSAPP_DRAFTS=1` is set and that you restarted the bridge.
2. Check `WHATSAPP_DRAFT_CHATS` and `WHATSAPP_DRAFT_SKIP_CHATS`. The customer's chat must be allowed and not skipped.
3. Wait for the delay. The default is 90 seconds after the last message.
4. Look in the bridge log for `Draft for ... failed`. The text after it gives the cause. A common cause is that `claude` or `python3` is not found. Set `CLAUDE_BIN` or `GHOSTWRITER_PYTHON`.
5. Try the `curl` command above. It shows the error directly.
6. Drafts that sound generic, or ignore your templates, can mean the runner reads another folder than your skills wrote to. Check that `GHOSTWRITER_HOME` is the same in both places, or unset in both.

**You do not get a notification for automatic drafts.** WhatsApp is quiet for messages that you send to yourself. Pin the "Message yourself" chat, and turn on notifications for it on your phone.

## License

MIT. See [LICENSE](LICENSE).
