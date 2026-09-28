# Install the Solnest Content Studio

Claude: the person pasted a link to this file into Claude Code. Follow it exactly, one
step per message. You run every command yourself with your Bash tool (Windows without
Git Bash: your PowerShell tool). The attendee never opens a terminal. Never ask for an
API key in the chat, and never print one.

## 1. Run the installer for this computer

Tell them in one line what is about to happen ("installing the Content Studio, about a
minute, nothing for you to do"), then run the line for their OS:

**Windows** (works from Bash and from PowerShell):

```
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/Solnest-AI/solnest-cinematic-director-cc/main/install.ps1 | iex"
```

**Mac:**

```
curl -fsSL https://raw.githubusercontent.com/Solnest-AI/solnest-cinematic-director-cc/main/install.sh | bash
```

It puts the skill in `~/.claude/skills/solnest-cinematic-director`, finds Python (or
installs one through uv, the way the STR Secrets Connections kit does), downloads ffmpeg
into the skill's own folder if the machine has none, picks up the KIE key from the
Connections kit if it is there, checks the KIE balance, and ends with a checklist. No
admin rights, nothing added to PATH, no questions. One to three minutes on the first run.
Use a generous tool timeout (10 minutes): the ffmpeg download is 30 to 60 MB.

Show the attendee the checklist it printed.

## 2. Read the checklist

- Every line `[ok]` and it ends with `ALL SET`: done. Tell them to quit and reopen Claude
  Code, then say **make me a Solnest video for &lt;listing url&gt;**.
- `[!!] KIE key`: the installer created the `.env` file and opened it for them. They get
  a key at https://kie.ai/api-key (sign in with Google, Create New Key, no IP whitelist),
  paste it after `KIE_API_KEY=` in that file, save, and tell you "saved". Then run the
  step 1 line again. Do not ask for the key in the chat.
- `[!!] balance` under 455 credits: one video costs about $2.28 (455 credits). They top up
  at https://kie.ai/billing ($5 minimum). Not a blocker for the install; say it once.
- `[!!] ffmpeg`: the download failed, usually the network. Run step 1 once more (it tries
  several mirrors). If it fails again: Windows `winget install --id Gyan.FFmpeg -e`, Mac
  `brew install ffmpeg`, then quit and reopen Claude Code and run step 1 again.
- `ERROR: no working Python`: run step 1 once more; if it repeats, send the full output to
  Ryan (ryan.lefebvre@strsecrets.com).

## 3. Update or repair later

Run the step 1 line again. It replaces the skill's scripts with the latest version and
keeps the `.env` and the downloaded ffmpeg.
