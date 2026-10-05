# Working on the project

Everyone works the same way, the owner included. `main` is the version the website shows. Nobody changes
it directly. Every change goes through a **pull request (PR)**: a proposal that everyone can look at,
comment on and discuss, and that the owner merges into `main` once it is agreed.

```
pull main → new branch → edit → preview → commit + push → open PR → discuss / revise → owner merges → pull main
```

You can type every command below yourself, or ask Claude in the Code tab to do it ("start a branch for
…", "open a PR", "pull the latest main"). Either way, the steps are the same.

---

## 1. Start from the latest `main`

```bash
cd ~/GitHub/sci-arc-studio-fall2026
git switch main
git pull
```

## 2. Make a branch for one piece of work

Use `<yourname>/<topic>`, short and lowercase:

```bash
git switch -c clark/terrace-massing
```

Use one branch per topic. A small PR is easier to discuss than a big one.

## 3. Make the change

**Website** (`web/`): edit the HTML, JS or `web/config.json`. Display names, layer colours, the
highlight colour and camera views all live in `config.json`. Preview with `python3 web/serve.py` and
reload the browser after each edit.

**3D model** (Blender):

1. Open `site-model/blender/y1_context.blend`. If you don't have it yet, build it first; see
   [SETUP §6](SETUP.md#6-blender).
2. Model in **your own collection**: `Design`, `Option_A`, `Clark_Terraces`, and so on. Never put
   hand-made work in `Terrain`, `Buildings`, `Y1_Parcel`, `Landmarks` or `Trees`; the scripts rebuild
   those from scratch.
3. Export: in Blender's Text Editor open `site-model/scripts/export_glb.py` and click **Run Script**. You
   can also ask Claude to "export the GLB". This writes `site-model/exports/context.glb`.
4. Preview with `python3 web/serve.py`. Your new collection appears as a layer toggle by itself. To give
   it a nicer name, an order or a colour, add an entry under `"layers"` in `web/config.json`.
5. Save the `.blend`. It is **not** stored in git, so keep your own backup copy of it.

> `build_all_blender.py` creates the `.blend` **from an empty scene**. Run it only to make a fresh file.
> Don't run it over a file that holds your own collections.

**Notes and research** (`site-model/BACKLOG.md`, `docs/`): plain Markdown.

## 4. Commit and push

```bash
git status                     # check: only the files you meant to change
git add web/config.json site-model/exports/context.glb
git commit -m "Add terrace massing option as Design layer"
git push -u origin clark/terrace-massing
```

Write the commit message as a short sentence saying *what changed*. Add files by name rather than
`git add .`, so nothing unexpected slips in.

**Never commit:**
- reference drawings, PDFs, photos or screenshots from the EIR, the press or archives (copyright). Keep
  them in `site-model/references/`, which git ignores;
- `.blend` files, the LiDAR `.laz` tile, or anything over about 50 MB;
- passwords, tokens or API keys.

## 5. Open a pull request

```bash
gh pr create --fill --web
```

This opens the PR form in the browser. Say **what** you changed, **why**, and **how to look at it**: for
example, *"Mesh mode, Design layer on, view 4th & Hill"*. Add a screenshot if it helps.

## 6. Discuss and revise

Comments arrive on the PR page on GitHub (and by email). To answer with a change, edit on the **same
branch**, then commit and push again. The PR updates automatically; there is no need to open a new one.

```bash
git add <files>
git commit -m "Lower terrace 2 by one storey, per review"
git push
```

## 7. Approve and merge (owner)

`main` is protected. A PR can only merge once the owner (the code owner in `.github/CODEOWNERS`) has
approved it, and pushing new commits clears an earlier approval. Once everyone agrees:

1. **Someone else's PR:** the owner opens **Files changed → Review changes → Approve → Submit review**,
   then clicks **Merge pull request**.
2. **The owner's own PR:** GitHub doesn't let you approve your own PR, so the owner ticks **Merge
   without waiting for requirements to be met (bypass rules)** and then merges.

Nobody, the owner included, can push to `main` directly, force-push it or delete it. GitHub then
publishes `main` to the live site within a few minutes. The PR page, with its discussion and every commit, stays in the
history permanently.

## 8. Tidy up

```bash
git switch main
git pull
git branch -d clark/terrace-massing
```

Then start the next piece of work back at step 2.

---

## Things to know

**`context.glb` is a single file.** Git can't combine two versions of it, so the most recently merged
export wins. If someone else's model change was merged while you were working, the export from your
`.blend` won't include it. Before you export:

1. Pull `main`.
2. If `context.glb` changed, bring the other person's collection into your `.blend`. In Blender use
   **File → Import → glTF** on `site-model/exports/context.glb`, keep only their collection, and delete
   the rest. You can also ask Claude to do this.
3. Then export.

Say in the PR that it updates the model, so two model PRs aren't open at the same time.

**Generated files.** `web/data/lidar_*.bin` and the files in `site-model/data/` come from the pipeline
scripts. Change the scripts, not the outputs. Commit the outputs together with the script change that
produced them.

**Ask early.** A draft PR (`gh pr create --draft`) is a good way to show half-finished work and ask
"is this the right direction?".

**Where things are.** [README](../README.md) gives the project overview and the pipeline.
[`CLAUDE.md`](../CLAUDE.md) holds the conventions: coordinates, units and data sources.
[`site-model/BACKLOG.md`](../site-model/BACKLOG.md) is the to-do list and the plans.
