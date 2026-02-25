# 🎚 FlowStation — For Artists

**Professional AI-powered songwriting tool for independent rappers, R&B artists, and producers.**

---

## What's In This Folder

```
FlowStation/
├── index.html       ← The entire app (all-in-one file, no dependencies)
├── netlify.toml     ← Netlify configuration (required — do not delete)
└── README.md        ← This file
```

Everything the app needs is inside `index.html`. Fonts and APIs load automatically from the internet when someone uses the app. There are no other files to manage.

---

## Features

| Feature | Description |
|---|---|
| ✍️ Smart Notepad | Write with live syllable counts on every line |
| 🎵 Auto Rhymes | Rhymes appear automatically as you type |
| 📖 1,000+ Starters | 16 categories: Flex, Faith, Love, Struggle, Hype & more |
| 🔍 Rhyme Dictionary | Powered by Datamuse / RhymeZone API |
| 📚 Thesaurus | Synonyms, antonyms, and related words |
| 🔤 Dictionary | Full English definitions, pronunciation, examples |
| 🎯 Hook Formulas | 10 structural templates for writing hit hooks |
| 🎚 BPM Guide | Syllable targets matched to tempo ranges |
| 🤖 AI Songwriting Coach | Powered by Anthropic Claude |
| 🎵 Beat Player | Upload any audio file and write along to it |
| 🎨 Rhyme Map | Color-codes your rhyme scheme visually |
| 🎲 Surprise Me | Random phrase generator to break writer's block |
| ⬇️ Export | Save your lyrics as a .txt file |
| 🌙 Mood Filter | Filter all 1,000+ starters by current vibe |

---

## How to Deploy on Netlify

### OPTION A — Drag and Drop (Fastest — No GitHub Needed)

**Step 1.** Go to [netlify.com](https://netlify.com) and sign in (or create a free account — takes 1 minute).

**Step 2.** On your dashboard, click the **"Add new site"** button.

**Step 3.** Click **"Deploy manually"**.

**Step 4.** A large dashed drop zone appears. Drag and drop the **entire `FlowStation` folder** (not just `index.html` — the whole folder) into that box.

**Step 5.** Wait 10–20 seconds. Netlify deploys it automatically.

**Step 6.** You get a live URL like `https://stellar-name-abc123.netlify.app` — that's your app, live on the internet.

**Step 7 (Optional).** Click **"Site settings" → "Change site name"** to get a cleaner URL like `flowstation-pro.netlify.app`.

---

### OPTION B — GitHub + Netlify (Best for Ongoing Updates)

Use this if you want to update the app easily in the future. Every time you push a change to GitHub, Netlify auto-deploys it.

**Step 1.** Log into [github.com](https://github.com). Click the **+** icon → **"New repository"**. Name it `flowstation`. Set it to **Private**. Click **"Create repository"**.

**Step 2.** On the new repo page, click **"uploading an existing file"**. Drag all three files from your `FlowStation` folder into the upload area. Click **"Commit changes"**.

**Step 3.** Go to [netlify.com](https://netlify.com). Click **"Add new site"** → **"Import an existing project"** → **"Deploy with GitHub"**.

**Step 4.** Connect your GitHub account when prompted. Select the `flowstation` repository.

**Step 5.** On the build settings page — leave everything blank. Just click **"Deploy site"**.

**Step 6.** Done. Every time you update files in GitHub, your site updates automatically within 30 seconds.

---

### Setting a Custom Domain

1. Buy a domain from [Namecheap](https://namecheap.com) or [Google Domains](https://domains.google) (e.g., `flowstation.io`)
2. In Netlify: **Site settings → Domain management → Add a domain**
3. Enter your domain and follow the DNS instructions Netlify shows
4. Netlify sets up HTTPS/SSL automatically — free certificate included
5. Takes 5–30 minutes for the domain to go live

---

## Password Protection (3 Options)

### Option 1 — Netlify Site Password ⭐ Recommended
**Cost:** Requires Netlify Pro ($19/month)
**Best for:** Simple, one-password access for all customers

1. Upgrade to Netlify Pro at [netlify.com/pricing](https://netlify.com/pricing)
2. Go to your site dashboard → **Site settings** → **Access control**
3. Under **"Basic password protection"**, click **Enable**
4. Set your password (example: `FlowStation2024`)
5. When customers buy, your automated email sends them: the URL + the password
6. They visit the site, enter the password, they're in

**To update the password:** Go back to the same setting and change it. Notify existing customers of the new password.

---

### Option 2 — Netlify Identity (Free Tier Available)
**Cost:** Free up to 1,000 users
**Best for:** Individual accounts per customer — each person has their own login

1. In Netlify: **Site settings → Identity → Enable Identity**
2. Under **Registration preferences**, select **"Invite only"**
3. When someone buys your product, go to **Identity → Invite users** and enter their email
4. They receive an email invitation, create their own password, and log in at your site URL
5. To remove a customer's access, delete their Identity user

---

### Option 3 — Netlify Edge Functions (Free — Technical)
**Cost:** Free
**Best for:** Developers or if you want a custom solution without paying for Pro

This requires adding a few extra files and some code. Recommended only if you have developer help. Ask a developer to implement "Netlify Edge Functions password gate."

---

## Setting Up the AI Coach

The AI Songwriting Coach requires an Anthropic API key. You have two options:

### Option A — Each customer provides their own key (Free for you)
- Customer clicks **"⚙ AI Key"** in the top bar of FlowStation
- They visit [console.anthropic.com](https://console.anthropic.com), create a free account, and copy their API key
- They paste it into FlowStation — it saves in their browser only, never transmitted to any server
- Anthropic charges are billed directly to their account (extremely cheap — pennies per session)

### Option B — You provide your key (You absorb the cost, seamless for customer)
1. Create an account at [console.anthropic.com](https://console.anthropic.com)
2. Generate an API key
3. Open `index.html` in a text editor (Notepad on Windows, TextEdit on Mac, or [VS Code](https://code.visualstudio.com))
4. Use **Find** (Ctrl+F / Cmd+F) to search for this exact text:
   ```
   let apiKey = localStorage.getItem('fs_key') || '';
   ```
5. Replace it with:
   ```
   let apiKey = localStorage.getItem('fs_key') || 'sk-ant-YOUR-KEY-HERE';
   ```
6. Save the file and re-upload to Netlify
7. Now every customer gets AI automatically with no setup required

**Cost estimate for Option B:** Approximately $0.003–$0.01 per AI conversation. At 100 active monthly users, expect $5–30/month in API costs.

---

## Troubleshooting

**Rhyme / Dictionary / Thesaurus not working?**
These features require an internet connection. They use free public APIs — no accounts or keys needed. Just make sure the device is online.

**AI Coach button is greyed out / not responding?**
An Anthropic API key hasn't been set. Click **"⚙ AI Key"** in the top bar and enter a valid key.

**The site looks broken or missing content?**
Make sure you dragged the whole `FlowStation` **folder** to Netlify, not just `index.html`. The `netlify.toml` file must be present alongside `index.html`.

**Audio player not working?**
Click **"+ Load Beat / Track"** at the bottom of the app and select a local audio file (MP3, WAV, M4A, FLAC). The player does not support streaming from URLs.

**How do I update the app after deploying?**
- If using drag-and-drop: Re-drag the updated folder to Netlify. It overwrites the previous version.
- If using GitHub: Replace the file in GitHub. Netlify auto-deploys in ~30 seconds.

**Can I run this locally without Netlify?**
Yes. Double-click `index.html` to open it in any browser. Most features work. The audio player may have limitations on some browsers when running from a local file.

---

## Tech Stack

- **100% static** — HTML5 + CSS3 + Vanilla JavaScript
- **No frameworks** — no React, no Node.js, no build steps
- **No backend** — everything runs in the browser
- **External APIs (internet required for these features):**
  - [Datamuse API](https://www.datamuse.com/api/) — rhymes + thesaurus (free, no key needed)
  - [Free Dictionary API](https://dictionaryapi.dev/) — definitions (free, no key needed)
  - [Anthropic Claude API](https://console.anthropic.com) — AI coach (API key required)
  - [Google Fonts](https://fonts.google.com) — Syne, JetBrains Mono, Outfit

---

## Suggested Pricing Model

| Tier | Price | What They Get |
|---|---|---|
| Basic | $9.99 one-time | Starters, rhyme, thesaurus, dictionary, syllable counter, beat player |
| Pro | $19.99/month | Everything + AI Coach (they provide their own API key) |
| Lifetime | $79 one-time | Everything forever, AI Coach included (you absorb API cost) |

The monthly Pro tier is where recurring revenue comes from. At 200 subscribers = $4,000/month.

---

*FlowStation — Built for artists who take their craft seriously.*
