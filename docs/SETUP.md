# Setting up

This guide takes you from nothing to working on the project: editing the website, the 3D site model and
the data, and proposing changes through pull requests. It is written for **macOS**.

Set up only as far as you need:

| Level | You can | You need sections |
|---|---|---|
| **0. Look** | Open the site model in a browser | none: open https://ruiw0211.github.io/sci-arc-studio-fall2026/ |
| **1. Website and content** | Change text, views, colours and pages; preview locally; open pull requests | 1–5 |
| **2. 3D model** | Edit the Blender model and export it to the website | 1–7 |
| **3. Data pipeline** | Re-run the LiDAR / terrain / building / tree processing | 1–8 |

Most people want level 2. Allow about an hour the first time.

> Every step ends with a **Check**: what you should see if it worked. If you see something else, stop
> there. Ask in the pull request or message Rui, and include a screenshot. These steps have not yet been
> run end to end on a Mac, so tell us whatever differs and we will fix this guide.

---

## 1. Homebrew, git, GitHub CLI and Python

Homebrew installs developer tools on a Mac. Open **Terminal** (Applications → Utilities → Terminal) and
paste:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

At the end it prints two or three lines under **Next steps**. Copy and run them; they add `brew` to your
PATH. Then install the tools:

```bash
brew install git gh python@3.12
```

**Check:** each of these prints a version number:

```bash
git --version
gh --version
python3 --version
```


## 2. GitHub account and access

1. Create a free account at https://github.com/signup.
2. Turn on email privacy: **Settings → Emails →** tick **Keep my email addresses private** and **Block
   command line pushes that expose my email**. GitHub then shows you a private address like
   `12345678+yourname@users.noreply.github.com`.
3. Send your GitHub username to the repository owner (Rui, GitHub `RuiW0211`). You will get an email
   invitation to `RuiW0211/sci-arc-studio-fall2026`. Accept it.
4. Sign in from Terminal:

   ```bash
   gh auth login --hostname github.com --git-protocol https --web
   ```

   It shows a one-time code and opens the browser. Enter the code and authorize. Wait in Terminal until
   it prints **Logged in as yourname** before closing anything.
5. Tell git who you are (your name, and the private address from step 2):

   ```bash
   git config --global user.name "Your Name"
   git config --global user.email "12345678+yourname@users.noreply.github.com"
   ```

**Check:** `gh auth status` says **Logged in to github.com account yourname**.


## 3. Get the project

```bash
mkdir -p ~/GitHub
gh repo clone RuiW0211/sci-arc-studio-fall2026 ~/GitHub/sci-arc-studio-fall2026
cd ~/GitHub/sci-arc-studio-fall2026
```

Keep the project **outside** iCloud Drive, Dropbox and OneDrive. Sync tools and git interfere with each
other. GitHub is the backup.

**Check:** `git log --oneline -3` lists recent changes.

## 4. Preview the website on your computer

```bash
python3 web/serve.py
```

Open http://localhost:8766/ in your browser and click **Site model viewer**. Stop the server with
**Ctrl + C**.

**Check:** the viewer loads. The **Model · Mesh** button shows the 3D model, and **LiDAR · Raw** shows
the point cloud.

`serve.py` serves the model the same way the live site does, so what you see locally is what will be
published.

## 5. Claude

1. Download the Claude desktop app for Mac from https://claude.ai/download and open it.
2. Sign in with your **Syracuse University** account (the Enterprise organisation).
3. Open the **Code** tab and choose the folder `~/GitHub/sci-arc-studio-fall2026`.

Claude reads `CLAUDE.md` in the project automatically, so it already knows the rules: work on a branch,
open a pull request, never push to `main`, never add copyrighted references. You can ask it in plain
language, for example *"make a branch and change the Overview camera so Y-1 is centred, then open a pull
request"*. Claude can run `git` and `gh` for you; you approve each step.

**Check:** ask Claude *"what is this project and what are the rules for contributing?"*. Its answer
should mention branches and pull requests.

---

*Level 1 ends here. Continue with [WORKFLOW.md](WORKFLOW.md) for the day-to-day routine.*

---

## 6. Blender

1. Download **Blender 5.2** (or the current 5.x) for **macOS Apple Silicon** (or Intel, if your Mac has
   an Intel chip) from https://www.blender.org/download/ and drag it into Applications.
2. Open it once from Applications. If macOS warns that it was downloaded from the internet, choose
   **Open**.
3. In Blender: **Blender menu → Settings → System → Network**, turn on **Allow Online Access**. The
   Claude connection needs this.

**Check:** in Terminal, this prints a version:

```bash
/Applications/Blender.app/Contents/MacOS/Blender --version
```

Build the project's Blender file. It is not stored in git; it is generated from the data in about 20
seconds:

```bash
/Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup --python site-model/scripts/build_all_blender.py
```

**Check:** it ends with `exported 690 objects`, or a similar number, and
`site-model/blender/y1_context.blend` now exists. Open that file in Blender.


## 7. Let Claude work inside Blender (Blender MCP)

The official Blender Lab MCP has two parts, from https://projects.blender.org/lab/blender_mcp/releases:
an add-on for Blender and an extension for Claude. Use the same release (version) for both.

1. **Blender add-on.** Download `mcp-<version>.zip`. In Blender: **Settings → Get Extensions →** the
   **⌄** menu at the top right → **Install from Disk…** → choose the zip. You can also drag the zip onto
   the Blender window. Then, in **Settings → Add-ons → MCP**, tick **Auto Start**. That way the bridge
   runs whenever Blender is open.
2. **Claude extension.** Download `blender-<version>.mcpb`. Double-click it, or in the Claude app open
   **Settings → Extensions** and install it from there. The exact wording of the menu can differ between
   app versions. Restart Claude afterwards.

**Check:** with Blender open, start a new Claude Code session and ask *"list the collections in the open
Blender scene"*. It should answer `Terrain, Buildings, Y1_Parcel, Landmarks, Trees`.

Your own modelling goes in **your own collections** (for example `Design` or `Option_A`). The build
scripts rebuild `Terrain`, `Buildings`, `Y1_Parcel`, `Landmarks` and `Trees` from scratch, and anything
hand-made inside those is lost on the next rebuild. Each collection becomes a layer toggle on the
website automatically.

*Level 2 ends here. The export routine is in [WORKFLOW.md](WORKFLOW.md#3-change-the-3d-model).*

---

## 8. Data pipeline (optional)

Only needed to change how the terrain, buildings, trees, LiDAR labels or the modeled population are
computed. The processed results are already in `site-model/data/` and `web/data/`.

```bash
cd ~/GitHub/sci-arc-studio-fall2026
python3 -m venv .venv
source .venv/bin/activate
pip install -r site-model/requirements.txt
python3 site-model/scripts/fetch_lidar.py      # downloads the 67 MB LiDAR tile (not in git)
```

The order of the pipeline scripts is in the [README](../README.md#rebuilding-the-site-model). Run
`source .venv/bin/activate` again in each new Terminal window.

**Check:** `fetch_lidar.py` ends with `saved …laz` or `already there`.

To change the population layer, edit `site-model/data/population/assumptions.json`, then run
`python3 site-model/scripts/prep_population.py` (about 30 s). It prints how many people are on site at
several hours; check those against the previous run before you open a PR.


---

## Troubleshooting

| Problem | Try |
|---|---|
| `brew: command not found` | Run the **Next steps** lines Homebrew printed, or open a new Terminal window |
| `gh auth login` returns before you authorized | Run it again and leave Terminal open until it says **Logged in** |
| `Permission denied` when pushing | Accept the repository invitation email, then re-run `gh auth login` |
| Viewer page is blank | Open it through `python3 web/serve.py`, not by double-clicking the HTML file |
| Claude can't see Blender | Blender must be open with the MCP add-on running (Settings → Add-ons → MCP); restart Claude after installing the extension |
| Something else | Copy the exact error and the command you ran into a pull request comment, or ask Claude in the Code tab |
