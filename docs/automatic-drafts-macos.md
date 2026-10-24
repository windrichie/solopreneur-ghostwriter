# Automatic drafts on a Mac: setup runbook

This runbook sets up automatic draft replies on a Mac. When a customer writes to the owner on WhatsApp, a draft reply arrives in the owner's own "Message yourself" chat about a minute and a half later. The owner copies it into the customer's chat and sends it. Nothing is ever sent to a customer automatically.

It is written for Claude Code to follow on the owner's behalf, one step at a time. A person can follow it too.

**Instructions for Claude Code:**
- The owner may not be technical. Before each step, say in one short, friendly sentence what you are about to do and why. Use no jargon.
- Do everything you can yourself. Stop and ask the owner only when a step needs them: a password, a click in a macOS dialog, the phone, or a choice.
- When the owner must type or paste something, give it as a single line they can copy.
- Check the result of each step before you go to the next one. If a check fails, explain the problem simply and fix it, or ask for help.
- Never print, copy or ask for passwords or API keys.
- Keep the bridge read-only: always set `WHATSAPP_READ_ONLY=1`. Never set `WHATSAPP_ALLOWED_RECIPIENTS` or `WHATSAPP_ALLOW_ANY_RECIPIENT`. The draft path sends only to the owner's own chat.
- Use the owner's own Claude account for drafts. If `claude auth status` shows a work or shared account, stop and ask the owner which account the business should use.

## What gets installed

| Item | Where | Why |
|---|---|---|
| Apple Command Line Tools | macOS | `git`, a C compiler and `python3` |
| Go | `/usr/local/go` | builds the WhatsApp bridge |
| Claude Code CLI | `~/.local/bin/claude` | writes the drafts |
| whatsapp-mcp | `~/Ghostwriter/whatsapp-mcp` | the bridge that connects to WhatsApp as a linked device |
| solopreneur-ghostwriter | `~/Ghostwriter/solopreneur-ghostwriter` | the draft writer and the learning skills |
| Voice, templates, facts | `~/.ghostwriter` | what the drafts learn from (private to this user) |
| Background service | `~/Library/LaunchAgents/com.solopreneur-ghostwriter.bridge.plist` | keeps the bridge running |
| Log | `~/Library/Logs/ghostwriter-bridge.log` | for troubleshooting |

The owner needs: this Mac (macOS 13 or later), the phone with the business WhatsApp (WhatsApp or WhatsApp Business), their own paid Claude account, and about 45 minutes.

## Step 1: Apple Command Line Tools

1. Run `xcode-select -p`. If it prints a path, skip to step 2.
2. Run `xcode-select --install`. Tell the owner: "A window will ask to install developer tools. Click **Install**, then **Agree**, and wait until it says the software was installed (5 to 20 minutes)."
3. Check: `xcode-select -p` prints a path, and `git --version` and `/usr/bin/python3 --version` both work.

## Step 2: Go

1. Run `go version` (also try `/usr/local/go/bin/go version`). If it prints `go1.21` or newer, skip to step 3.
2. Find the newest stable macOS installer: fetch `https://go.dev/dl/?mode=json` and take the first entry with `"stable": true`. Pick the file whose `os` is `darwin`, `kind` is `installer`, and `arch` is `arm64` on Apple silicon (`uname -m` prints `arm64`) or `amd64` on Intel.
3. Download it into `~/Downloads`, check its SHA-256 against the `sha256` field, then open it with `open ~/Downloads/<file>.pkg`.
4. Tell the owner: "An installer opened. Click **Continue** and **Install**, type your Mac password when it asks, then click **Close**."
5. Check: `/usr/local/go/bin/go version` works. Use `/usr/local/go/bin/go` by full path for the rest of this runbook. The repository asks for a newer Go toolchain, and Go downloads it on its own the first time it builds.

## Step 3: Claude Code CLI and sign-in

The drafts run through the `claude` command, separately from the Claude app.

1. Run `~/.local/bin/claude --version`. If it fails, install it: `curl -fsSL https://claude.ai/install.sh | bash`, then check the version again.
2. Run `~/.local/bin/claude auth status`. If `loggedIn` is false, ask the owner to open the **Terminal** app and paste this line, then sign in with their own Claude account in the browser:

   ```bash
   ~/.local/bin/claude auth login
   ```

3. Check: `~/.local/bin/claude auth status` shows `loggedIn: true` and the owner's email. Read the email back to the owner and confirm it is the account the business should use.

## Step 4: Download the code

```bash
mkdir -p ~/Ghostwriter
git clone https://github.com/windrichie/whatsapp-mcp ~/Ghostwriter/whatsapp-mcp
git clone https://github.com/windrichie/solopreneur-ghostwriter ~/Ghostwriter/solopreneur-ghostwriter
```

If a folder already exists, run `git -C <folder> pull` instead.

## Step 5: Build the bridge

```bash
cd ~/Ghostwriter/whatsapp-mcp/whatsapp-bridge && /usr/local/go/bin/go build -o whatsapp-client .
```

The first build downloads Go modules and can take a few minutes. Check: `~/Ghostwriter/whatsapp-mcp/whatsapp-bridge/whatsapp-client` exists.

## Step 6: Link WhatsApp

The bridge connects as a linked device, like WhatsApp Web. This happens once.

1. Start the bridge where the owner can see its output, in a terminal window or the app's terminal panel, not in the background:

   ```bash
   cd ~/Ghostwriter/whatsapp-mcp/whatsapp-bridge && WHATSAPP_READ_ONLY=1 ./whatsapp-client
   ```

2. When a QR code appears, tell the owner: "On your phone, open WhatsApp, go to **Settings** (iPhone) or the **⋮ menu** (Android), tap **Linked devices**, then **Link a device**, and point the phone at the QR code on screen."
3. A code lasts about 20 seconds, and a new one appears on its own. If the bridge stops waiting, start it again.
4. Check: the output shows `Connected to WhatsApp`, then several `History sync complete` lines. Wait until no new history lines appear for a minute, then stop the bridge with Ctrl-C.

## Step 7: Install the Ghostwriter skills

```bash
~/.local/bin/claude plugin marketplace add windrichie/solopreneur-ghostwriter
~/.local/bin/claude plugin install solopreneur-ghostwriter@solopreneur-ghostwriter
```

Check: `~/.local/bin/claude plugin list` shows `solopreneur-ghostwriter`. The skills load in Claude Code sessions started after the install.

## Step 8: Learn the owner's templates and voice

Run both skills with the owner, in a new Claude Code session, and let the owner check every result before it is saved:

- `/solopreneur-ghostwriter:learn-templates` with `--store-dir ~/Ghostwriter/whatsapp-mcp/whatsapp-bridge/store` (expand `~` to the full path).
- `/solopreneur-ghostwriter:learn-voice` with the same store folder.

The results go to `~/.ghostwriter`. Check that `voice.md`, `templates.md` and `facts.md` exist there and are not empty. Then ask the owner which facts are missing, such as address, opening hours, prices and payment methods, and add the ones they confirm.

## Step 9: Choose who gets drafts

Ask the owner: "Are there chats that should never get a draft, for example family and close friends?" Collect phone numbers with the country code and digits only (for example `6591234567`). Leave the list empty if there are none.

For a first test, it can also help to draft for one chat only: put one friend's number in `WHATSAPP_DRAFT_CHATS`, and remove it after the test.

## Step 10: Run the bridge in the background

Write `~/Library/LaunchAgents/com.solopreneur-ghostwriter.bridge.plist`. Use full paths: replace `/Users/USERNAME` with the real home folder (`echo $HOME`). Leave `WHATSAPP_DRAFT_SKIP_CHATS` empty or fill it from step 9.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.solopreneur-ghostwriter.bridge</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/USERNAME/Ghostwriter/whatsapp-mcp/whatsapp-bridge/whatsapp-client</string>
  </array>
  <key>WorkingDirectory</key>
  <string>/Users/USERNAME/Ghostwriter/whatsapp-mcp/whatsapp-bridge</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>WHATSAPP_STORE_DIR</key>
    <string>/Users/USERNAME/Ghostwriter/whatsapp-mcp/whatsapp-bridge/store</string>
    <key>WHATSAPP_READ_ONLY</key>
    <string>1</string>
    <key>WHATSAPP_DRAFTS</key>
    <string>1</string>
    <key>WHATSAPP_DRAFT_COMMAND</key>
    <string>/Users/USERNAME/Ghostwriter/solopreneur-ghostwriter/bin/draft</string>
    <key>WHATSAPP_DRAFT_DELAY_SECONDS</key>
    <string>90</string>
    <key>WHATSAPP_DRAFT_SKIP_CHATS</key>
    <string></string>
    <key>GHOSTWRITER_PYTHON</key>
    <string>/usr/bin/python3</string>
    <key>CLAUDE_BIN</key>
    <string>/Users/USERNAME/.local/bin/claude</string>
    <key>PATH</key>
    <string>/Users/USERNAME/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>/Users/USERNAME/Library/Logs/ghostwriter-bridge.log</string>
  <key>StandardErrorPath</key>
  <string>/Users/USERNAME/Library/Logs/ghostwriter-bridge.log</string>
</dict>
</plist>
```

Then:

1. Check the file: `plutil -lint ~/Library/LaunchAgents/com.solopreneur-ghostwriter.bridge.plist`.
2. Start it: `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.solopreneur-ghostwriter.bridge.plist`.
3. Tell the owner that macOS may show a "Background Items Added" notice. This is expected.
4. Check: after about 15 seconds, `tail -n 20 ~/Library/Logs/ghostwriter-bridge.log` shows `Connected to WhatsApp` and `Draft replies: on`.

## Step 11: Test it

1. Ask the owner to have a friend send them a WhatsApp message, and not to reply to it for two minutes.
2. Watch the log for `Draft for … sent to your own chat`.
3. Ask the owner to open the **Message yourself** chat (also called "You") on the phone. Two new messages should be there: a header that says who the draft is for, then the draft itself.
4. Tell the owner: WhatsApp does not notify you about messages to yourself. Pin the "Message yourself" chat to the top of the chat list, so new drafts are easy to see.

If no draft arrives, read the log. A line `Draft for … failed` says why. The most common causes:
- `claude` is not signed in: repeat step 3.
- The chat is in the skip list, or is not in `WHATSAPP_DRAFT_CHATS`: fix the plist and restart (see "Maintenance").

## Step 12: Keep the Mac awake

Drafts are made only while the Mac is awake. Messages that arrive while it sleeps get a draft when it wakes up, if they are less than 24 hours old.

Tell the owner: "Keep the laptop plugged in and open during work hours. In **System Settings → Battery → Options**, turn on **Prevent automatic sleeping on power adapter when the display is off**."

## How the owner uses it

1. A customer writes on WhatsApp.
2. About 90 seconds after their last message, the draft arrives in "Message yourself".
3. The owner long-presses the draft, taps **Copy**, opens the customer's chat, pastes it, edits it if needed, and sends it.
4. If the owner answers before the draft arrives, the draft is cancelled.

A draft can contain `[CHECK: …]` where a fact is missing (for example a price). The header then says what to check. Replace it before sending.

## Maintenance

| Task | Command or action |
|---|---|
| Restart after a settings change | `launchctl kickstart -k gui/$(id -u)/com.solopreneur-ghostwriter.bridge` |
| Pause drafts | `launchctl bootout gui/$(id -u)/com.solopreneur-ghostwriter.bridge` (start again with the `bootstrap` command from step 10) |
| Update | `git -C ~/Ghostwriter/whatsapp-mcp pull`, `git -C ~/Ghostwriter/solopreneur-ghostwriter pull`, repeat step 5, then restart |
| Add or change a template | in Claude Code: "Add this as my template for … : …" (learn-templates skill) |
| Drafts don't sound right | in Claude Code: run `/solopreneur-ghostwriter:learn-voice` again |
| WhatsApp was unlinked | stop the service (pause), repeat step 6, then start it again |
| See what happened | `tail -n 50 ~/Library/Logs/ghostwriter-bridge.log` |

WhatsApp signs out linked devices if the phone itself is not used for 14 days.

## Safety notes

- The bridge is read-only. The only message it ever sends is the draft, and only to the owner's own chat.
- The AI that writes drafts has no tools. It receives the chat and the owner's voice, templates and facts as text, and returns text.
- Each draft sends that chat's recent messages to Claude, under the Claude account that `claude` is signed in with.
- WhatsApp does not allow unofficial clients, and can ban accounts that use them. This setup keeps the risk low: it only reads messages and sends a few messages to the owner. It never messages customers. The risk is still not zero.
