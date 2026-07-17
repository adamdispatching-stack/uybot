# 🚀 Deploy: GitHub → Railway

Двойной клик по `deploy.bat` = изменения улетают на GitHub, Railway сам
переразворачивает приложение. / Double-click `deploy.bat` — Railway redeploys
automatically.

---

## One-time setup (10 minutes)

### 1. Git on your PC

Install Git for Windows if you don't have it: https://git-scm.com/download/win
(during install just click Next everywhere). Then in any terminal once:

```
git config --global user.name "CMJ"
git config --global user.email "cmjcollctrucking@gmail.com"
```

### 2. GitHub repo

Your repo is already set up in the scripts:
**https://github.com/adamdispatching-stack/uybot**

Just double-click **`setup_git.bat`** in the `uyweb` folder once.
On first push, a window will ask you to sign in to GitHub — sign in once,
Windows remembers it.

### 3. Railway

1. railway.app → **New Project** → **Deploy from GitHub repo** → pick `uybot`.
2. **Add a Volume** (right-click the service → Attach Volume), mount path: `/data`.
   ⚠️ Without this, the database is ERASED on every deploy — Railway's disk is
   temporary. The volume keeps `realestate.db` safe.
3. Service → **Variables** → add:
   | Variable     | Value                    |
   |--------------|--------------------------|
   | `DB_PATH`    | `/data/realestate.db`    |
   | `PHOTOS_DIR` | `/data/photos`           |
   | `BOT_TOKEN`  | your @BotFather token (optional, for Telegram reminders) |

   (`PHOTOS_DIR` keeps uploaded house photos on the volume so they survive deploys.)
4. Service → **Settings → Networking → Generate Domain** — you get a free
   HTTPS address like `uyweb-production.up.railway.app`.
   Give this link to your brother — it opens on any phone.

That's it. The app reads Railway's `PORT` automatically.

---

## Daily use

- Change any file → double-click **`deploy.bat`** → done.
  Railway rebuilds in about a minute.
- Custom commit message (optional): open cmd in the folder and run
  `deploy.bat fixed rent report`
- The HTTPS Railway address also works as a **Telegram Mini App**:
  @BotFather → your bot → Bot Settings → Menu Button → paste the URL.

## Notes

- `.gitignore` keeps `realestate.db` out of GitHub — the live database lives
  only on the Railway volume, your local test data never overwrites it.
- Backup of the live DB: Railway → service → Volume → download, or add
  a backup endpoint later if needed.
- If `deploy.bat` says push failed: check internet, or sign in to GitHub again
  (Windows Credential Manager → remove github entry → push again).
