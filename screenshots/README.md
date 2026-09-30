# Screenshots

Drop images in this folder with these exact names and they'll appear in the main
README automatically:

| Filename | What to capture | How |
|---|---|---|
| `wall.jpg` | **The best shot** — a photo of the monitor running on your wall | Phone camera, straight-on, lights on |
| `hub.jpg` | The Hub (calendar / lists / meals / countdowns) | Photo of the wall on Hub, **or** open `http://familycal.local:8000/` on a laptop and screenshot |
| `music.jpg` | The lyric screen | Play something on Spotify, **or** open `…:8000/music?demo=1` (demo lyrics, no Spotify needed) |
| `gallery.jpg` | The photo gallery + rail | `…:8000/gallery` |
| `remote.jpg` | The phone remote | Open `familycal.local:8000/remote` on your phone → screenshot |
| `meals.jpg` | The meal planner + suggestions | Open `…:8000/meals` on your phone → screenshot |

## Two easy ways to add them

**A. In the browser (easiest):** open the repo on github.com, edit `README.md`,
and just **drag an image into the editor** — GitHub uploads it and inserts the
link for you. (You can drop them right into the Screenshots table.)

**B. In the folder:** copy the files here with the names above, then:
```bash
git add screenshots/*.jpg && git commit -m "Add screenshots" && git push
```

Tip: the wall is portrait, so wall/Hub/gallery/music shots will be **tall**;
the phone shots (remote, meals) are tall too. That's fine — they'll sit neatly
side-by-side in the README table.
