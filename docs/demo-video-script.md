# ai-identicon — demo video script

A showcase + explainer for **ai-identicon**: generative, animated avatars
("presence orbs") for AI agents. Told **first person** — it opens and closes
on *your* story (building thousands of AI assistants) and shows the tool in
between. Target length **~3–3.5 min** (a 60‑sec cut is marked at the end).
Format per beat: **[SCREEN]** what's visible · **[DO]** what to click ·
**[VO]** what to say.

Recording setup:
- Run `python examples/gallery.py`. Window ~980×660; put it on a dark desktop.
- Have the gallery at the default seed to start (a violet 2‑shard crystal).
- Record at 1080p; the orb animates at 60fps, so use a screen recorder that
  captures smooth motion. Move the mouse deliberately and pause on each state
  for ~2 seconds so viewers can read the motion.
- Optional: a second app open (Obsidian / Discord / a chat) for the paste demo.

---

## 1 · Hook — the personal why (0:00–0:35)

**[SCREEN]** Open on the live orb at **idle** — slowly breathing, the odd
blink. Fill the frame with just the orb (crop out the panel, or blur it).
Optional: on the "creepy / cheesy" lines, cut to a beat of uncanny AI‑face
b‑roll and a cartoon‑assistant clip, then return to the orb.

**[VO — first person, straight to camera energy]**
> I'm going to build **thousands** of AI assistants this year. Thousands.
>
> And it hit me that every one of them needs to be someone you can
> *recognize* — its own presence. Almost like a face.
>
> But "face" is a trap. Make it look human and it's instantly creepy — that
> uncanny‑valley wrongness, like it's watching you. Make it a cartoon mascot
> and it's cheesy. Neither is what I want standing in for an intelligence.
>
> So I built a different kind of face. This is **ai-identicon**.

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

## 7 · The serious part + intrigue outro (2:55–3:25)

**[SCREEN]** Back to the live orb (idle), or the color portrait. Optionally
show the GitHub repo page, then the end card.

**[VO]**
> It's deterministic and versioned — an agent's face is frozen the day it's
> born and never silently changes. Zero‑dependency Python core, optional live
> renderer, open source, MIT.
>
> But here's the thing: this is just the *face*. And it brings me back to
> where I started —
>
> How does one person build *thousands* of AI assistants? And what are they
> all going to be *for*?
>
> Follow along to find out. This is where it starts.

**[SCREEN]** End card: `github.com/seriouscoderone/ai-identicon` + your handle
/ "follow for what's next".

---

## 60‑second cut

Use beats **1** (hook — trim to just "I'm building thousands of AI assistants…
so what should they look like?", 0:00–0:14), **2** (dice through a few seeds,
0:14–0:26), **3** (states — idle → listening → thinking → speaking only,
0:26–0:44), **6** (portraits + one paste, 0:44–0:52), **7** (intrigue outro —
"how does one person build thousands? follow to find out" + repo card,
0:52–1:00).

## Screenshot suggestions (for the still)

- **Hero:** the live orb mid‑**thinking** with the `glow` style — the inner
  light + averted gaze reads as "an AI is here, working."
- **Range shot:** 🎲 a handful of seeds and grab a **crystal** or **glass** one
  in **listening** (the ring + facing‑you pose is legible).
- **Product shot:** click **view 🎨** and capture the four‑size color quad — it
  instantly communicates "this scales from big to a 40px avatar."
