# ai-identicon — demo video script

A showcase + explainer for **ai-identicon**: generative, animated avatars
("presence orbs") for AI agents. Target length **~2.5–3 min** (a 60‑sec cut is
marked at the end). Format per beat: **[SCREEN]** what's visible ·
**[DO]** what to click · **[VO]** what to say.

Recording setup:
- Run `python examples/gallery.py`. Window ~980×660; put it on a dark desktop.
- Have the gallery at the default seed to start (a violet 2‑shard crystal).
- Record at 1080p; the orb animates at 60fps, so use a screen recorder that
  captures smooth motion. Move the mouse deliberately and pause on each state
  for ~2 seconds so viewers can read the motion.
- Optional: a second app open (Obsidian / Discord / a chat) for the paste demo.

---

## 1 · Hook (0:00–0:20)

**[SCREEN]** The live orb at **idle** — slowly breathing, the occasional blink.
Fill the frame with just the orb (crop out the panel if you can, or blur it).

**[VO]**
> Every AI agent needs an identity. But give it a human face and it's
> creepy — give it a cartoon mascot and it's cheesy. So what does an agent
> actually *look* like?
>
> This is **ai-identicon**. It grows a unique, living "presence" for any agent
> — deterministically, from nothing but a seed string.

---

## 2 · The concept: identicons, but alive (0:20–0:45)

**[DO]** In the **Seed** box (top right), type a name — e.g. `alice` — press Enter.
Then type `bob`, Enter. Then click the **🎲** dice button 3–4 times.

**[SCREEN]** Each seed snaps to a completely different orb — different shape,
color, material, number of shards.

**[VO]**
> You've seen GitHub's little pixel identicons. Same idea — a seed becomes a
> picture — but here the seed becomes a faceted 3‑D form that *moves*. The same
> seed always produces the same orb, forever. Different seeds look clearly
> different. In a real app the seed is the agent's identifier, so every agent
> gets its own recognizable face.

---

## 3 · It's alive: the states (0:45–1:25)

**[DO]** Type the seed `alice` (or pick one you like) so the shape is stable,
then click each **state button** along the bottom, pausing ~2s on each. Read
the caption line under the orb as you go.

Walk them in this order:

1. **idle** — *[VO]* "At rest, it just breathes."
2. **listening** — *[VO]* "When it's listening, it turns to face you, and
   ripples drift inward — like sound arriving." *(point out it squares up)*
3. **thinking** — *[VO]* "Thinking: it looks away, down and to the side, its
   surface fragments while it works — then pulls back together."
4. **speaking** — *[VO]* "Speaking draws its voice as a waveform around it."
   *(if you'll do the mic bit, mention it here)*
5. **notify** — *[VO]* "A notification is a quick chirp and an excited little
   spin…" *(it returns to idle on its own)*
6. **success** — *[VO]* "…success, a warm pulse…"
7. **error** — *[VO]* "…and an error makes it seize up and flush amber."

**[VO] (closing the section)**
> None of this is a face. It reads as *presence* — attention, thought, voice —
> through motion and light alone. Present, but never pretending to be human.

---

## 4 · Personality: same states, different character (1:25–1:50)

**[DO]** Keep one seed. In the right panel, change the **Thinking** dropdown
through its options while the orb is in the **thinking** state: `breakup`,
`glow`, `shimmer`, `orbiter`. Then nudge the **Expressive** and **Tempo**
sliders up and down.

**[SCREEN]** The thinking animation changes character — pieces drifting, an
inner glow, a light wave, orbiting sparkles. Sliders make it bigger/faster.

**[VO]**
> Every agent also has a seeded *personality* — how energetically and how fast
> it performs those states, and which "thinking" gesture is its own. Two agents
> can share a shape but move completely differently.

---

## 5 · The genome: what makes each orb (1:50–2:15)

**[DO]** With any seed, sweep a few sliders so viewers see cause/effect:
- **Shapes** 1 → 5 (it fragments into more pieces).
- **Fragmentation** low → high (compact cracked stone → scattered cluster).
- **Material** dropdown: `stone` → `crystal` → `metal` → `glass` (matte rock,
  bright gem, metallic sheen, frosted glass).
- **Hue** slider (recolor), **Roughness**, an **Elong** axis (stretch it).

**[VO]**
> Under the hood each orb is grown from a genome: how many shards, how broken,
> how rough, how stretched, its material, its color. All of it seeded — these
> sliders just let you explore the space. And it's built to be *believable*:
> the pieces collide instead of overlapping, and no shard is ever a flat,
> sharp sliver.

---

## 6 · Get it out: portraits + clipboard (2:15–2:40)

**[DO]** Click **view ⬜**, **view ⬛**, **view 🎨** in turn — the quad preview
shows the static portrait at four sizes (down to a 40px avatar). Then click
**copy 📋**, switch to Obsidian / Discord / a chat, and **paste** (⌘V).

**[SCREEN]** The line-art and color portraits; then the avatar pasting into a
real app as an image.

**[VO]**
> Beyond the live view, every orb exports as a clean SVG — filled color, or
> line art for light and dark backgrounds — tuned to stay readable even at
> tiny avatar sizes. And you can copy one straight to your clipboard as a PNG
> and drop it into Obsidian, Teams, Discord, anywhere.

---

## 7 · The serious part + outro (2:40–3:00)

**[SCREEN]** Back to the live orb (idle), or the color portrait. Optionally
show the GitHub repo page.

**[VO]**
> It's deterministic and versioned — an agent's face is frozen the day it's
> born and never silently changes. It's a zero‑dependency Python core with an
> optional Qt renderer, MIT‑licensed and open source.
>
> ai-identicon — a face for your agents that's neither creepy nor cheesy.
> On GitHub now.

**[SCREEN]** End card: `github.com/seriouscoderone/ai-identicon`

---

## 60‑second cut

Use beats **1** (hook, 0:00–0:12), **2** (dice through a few seeds, 0:12–0:25),
**3** (states — idle → listening → thinking → speaking only, 0:25–0:45),
**6** (portraits + one paste, 0:45–0:55), **7** (outro + repo card, 0:55–1:00).

## Screenshot suggestions (for the still)

- **Hero:** the live orb mid‑**thinking** with the `glow` style — the inner
  light + averted gaze reads as "an AI is here, working."
- **Range shot:** 🎲 a handful of seeds and grab a **crystal** or **glass** one
  in **listening** (the ring + facing‑you pose is legible).
- **Product shot:** click **view 🎨** and capture the four‑size color quad — it
  instantly communicates "this scales from big to a 40px avatar."
