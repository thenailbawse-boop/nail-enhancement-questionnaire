# Where words go on Anisia's videos (her rule)

Anisia's rule: **all words go at the top of the screen. Never on her face, and never on the
main subject of the shot** (the person, the stage, the food).

Tested on her phone in Instagram Reels, 2026-11-19 (Black Beauty Block Party recap).

## Exact spot, on a 1080 x 1920 video

- **Top of the words: y = 300.** Instagram's "< Reels +" header covers about the top 235 px.
  At y = 175 the words ran into the header (seen in her screenshot), so stay at 300 or lower.
- **Keep every line 780 px wide or less, centred** (from x = 150 to x = 930).
  Instagram zooms a 9:16 video to fill a tall phone and trims about 97 px off each side,
  so only about x = 97 to 983 shows. A 940 px line got its edges cut off.
- **Right-aligned words** (used when faces fill the middle): right edge at x = 940, at most 380 px wide.
- **Size:** Montserrat ExtraBold (her "Bold Caps"), up to 70 px, shrunk to fit. Line height 1.2x.
  At most 2 lines (3 for short words in a corner). Split long lines in two instead of shrinking a lot.
- **Look:** white words with a dark outline and a soft shadow. Key words in her pink #F4A6C4.
  No black title screens and no full-screen end card: she doesn't like them.
  Put the ending line over the last clip, in the top area.

## Before sending

- Look at a frame from every shot and move the words if they touch a face.
  When a face rises into the top area, end the words early or move them to the empty corner.
- Check a preview cropped the way Instagram shows it: crop=886:1920:97:0, with the top 235 px marked.

## Tool

`brand-assets/words-over-clips.py` draws the word cards (times, lines, pink words, alignment)
with these settings. It is the script used for the Block Party recap: change the CARDS list for a new video.

```bash
python words-over-clips.py WORDS_DIR > WORDS_DIR/times.txt      # makes w0.png, w1.png ... and their times
ins=(-i "$VIDEO"); fc=""; last="0:v"; n=1
while read i s e; do
  ins+=(-loop 1 -framerate 30 -t 999 -i WORDS_DIR/w$i.png)
  fo=$(python3 -c "print(round($e-0.15,2))")
  fc+="[$n:v]format=rgba,fade=t=in:st=$s:d=0.15:alpha=1,fade=t=out:st=$fo:d=0.15:alpha=1[o$n];[$last][o$n]overlay=0:0:enable='between(t,$s,$e)'[v$n];"
  last="v$n"; n=$((n+1))
done < WORDS_DIR/times.txt
ffmpeg -y "${ins[@]}" -filter_complex "${fc%;}" -map "[$last]" -map 0:a -shortest \
  -c:v libx264 -crf 17 -pix_fmt yuv420p -c:a copy -movflags +faststart OUT.mp4
```
