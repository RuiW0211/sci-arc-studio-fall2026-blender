# Contributing

New here? Start with these two guides:

1. **[docs/SETUP.md](docs/SETUP.md)**: install the tools (macOS, with Windows notes), get a GitHub
   account and access, clone the project, and connect Claude and Blender.
2. **[docs/WORKFLOW.md](docs/WORKFLOW.md)**: the day-to-day routine: branch, edit, preview, open a pull
   request, discuss, merge.

The rules in short:

- Don't push to `main`. Every change is a pull request from a branch named `<yourname>/<topic>`, and
  the owner merges it after discussion.
- Put hand-made Blender work in its own collection. The build scripts rebuild `Terrain`, `Buildings`,
  `Y1_Parcel`, `Landmarks` and `Trees`.
- Never commit copyrighted references (drawings, photos, PDFs), `.blend` or `.laz` files, or secrets.
- Keep everything in EPSG:26911 metres, NAVD88 heights, origin E 384580 / N 3768520. See
  [CLAUDE.md](CLAUDE.md).
