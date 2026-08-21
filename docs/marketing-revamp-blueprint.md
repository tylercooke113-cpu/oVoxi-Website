# oVoxi Website Revamp
## Creative Direction and Front End Architecture Blueprint

Version 1.0 · For Tyler Jatzeck-Cooke · Build target: existing CRA/CRACO repo, in place

---

# PART 1: THE STRATEGY

## 1.1 What this site is actually for

The current site is a product entry point. The new site has a harder job: it is the first thing a stranger sees after a cold email, and that stranger is one of three very different people.

| Who | What they fear | What they need to feel | What they do next |
|---|---|---|---|
| **AI platform BD and legal** (Suno, Udio, Klay Vision, Mirelo) | Getting sued over training data | Safe. Covered. Documented. | Book a call, request a sample pack |
| **Investors** (OpenVC, Pickwick, angels) | Backing a company with no moat | Early. Ahead of consensus. | Request the deck |
| **Emerging artists** (the 2,500) | Being exploited again | Seen. Chosen. Not the product. | Start an application |

These three want opposite tones. The buyer wants institutional seriousness. The artist wants warmth and respect. Trying to serve both in one linear scroll produces a site that serves neither.

**The unifying emotion is being early.** The AI platform is early to clean supply. The investor is early to the category. The artist is early to a revenue stream that does not exist yet. That is the same feeling wearing three coats, and it is already your positioning word: Emerging-First.

So the site opens with one shared cinematic statement about being early, then forks. It does not try to be one thing to everyone.

## 1.2 The competitive visual landscape

I looked at where the category actually sits visually:

- **Epidemic Sound, Artlist**: bright, warm, creator-economy friendly. Photography of people making things. Approachable, slightly generic.
- **Suno, Udio**: consumer-playful. Bright colors, rounded, app-like.
- **Rights infrastructure incumbents** (Merlin, Downtown, SoundExchange, PRO sites): institutional blue, dense text, dated. Trustworthy and forgettable.
- **AI audio infrastructure** (AudioShake and peers): clean technical startup. White, blue, sans-serif, competent, indistinguishable.

**The gap: nobody in music rights looks premium.** Everyone is either consumer-playful or institutionally dull. Your existing palette, pure black with a purple-to-blue gradient, is already the most premium-leaning asset in the category and you are currently underusing it.

**The direction: instrument-grade.** Closer to high-end audio hardware or a serious infrastructure company than to a music library. Black canvas, precise type, restrained color, one large cinematic motion idea. Confident enough to leave space empty.

**The risk I am taking, and why:** most sites in this category prove seriousness with density, meaning lots of logos, lots of stats, lots of copy. This site proves seriousness with restraint and one very expensive-looking motion sequence. The bet is that a buyer who is scared of litigation is reassured more by evident competence than by more words. If you disagree with that bet, say so now, because it governs every decision below.

---

# PART 2: VISUAL IDENTITY

## 2.1 Color

Locked palette, unchanged from brand:

```
--ovx-void          #000000   Canvas. Not near-black. Actual black.
--ovx-gradient-1    #B44FD4   Gradient start (magenta-purple)
--ovx-gradient-2    #7B5EA7   Gradient mid (violet)
--ovx-gradient-3    #6B7FD4   Gradient end (indigo-blue)
--ovx-cyan          #4FC3F7   Accent, interaction, links, focus rings
```

Derived neutrals, new, needed because black plus white alone cannot build a UI:

```
--ovx-surface       #0A0A0C   Card and panel fill. Barely lifted off black.
--ovx-line          #1C1C21   Hairline borders and dividers
--ovx-text          #FFFFFF   Primary text
--ovx-text-dim      #8A8A94   Secondary text and labels
--ovx-text-faint    #4A4A52   Metadata, footers, disabled
```

**The rule that makes this a system rather than a palette: the gradient means "cleared."**

The purple-to-blue gradient is never decoration. It appears only on things that have passed verification: a cleared track, a completed pipeline stage, a confirmed state. Uncleared and unverified things are grey. Cyan is the only interactive color, so anything cyan is clickable or focused, always.

This gives your brand color semantic meaning across the marketing site and the product. An artist who sees grey turn to gradient in the hero will recognize it later in their vault. That is worth more than any amount of decorative gradient.

## 2.2 Typography

Existing faces stay. Two changes and one addition.

| Role | Face | Notes |
|---|---|---|
| Display | **Syne 800** | Keep. It is genuinely distinctive and does heavy lifting for you already. Set tight: `letter-spacing: -0.02em`, `line-height: 0.95` at large sizes. |
| Body lead | **DM Sans 300** | Keep, but only above 20px. |
| Body | **DM Sans 400** | **Change.** DM Sans 300 at 16px on pure black is genuinely hard to read. Thin weights lose to the halation of white-on-black. 400 below 20px. |
| Data and technical | **JetBrains Mono 400** | **New.** For numbers, percentages, track IDs, status codes, pipeline labels. |

The mono is the addition worth defending. It separates claims from evidence. Marketing prose is DM Sans. Anything factual and checkable, a market size, a stem count, a clearance status, is mono. On a site whose whole argument is "we document things," a typeface that reads as instrument output does real work.

Type scale, 1.25 ratio, clamped for fluid sizing:

```
--fs-hero    clamp(3.5rem, 9vw, 8rem)      Syne 800
--fs-h1      clamp(2.5rem, 5vw, 4.5rem)    Syne 800
--fs-h2      clamp(1.75rem, 3vw, 2.75rem)  Syne 800
--fs-lead    clamp(1.125rem, 1.6vw, 1.5rem) DM Sans 300
--fs-body    1rem                           DM Sans 400
--fs-label   0.8125rem                      JetBrains Mono 400, uppercase, 0.12em tracking
--fs-data    clamp(2rem, 4vw, 3.5rem)       JetBrains Mono 400
```

## 2.3 Layout and structure

12-column grid, 1440px max content width, 120px gutters on desktop. Sections breathe: 160px vertical rhythm on desktop, 96px on mobile. Nothing is cramped.

**On numbered markers:** your deck uses 01 through 05 for the clearance pipeline. Keep that on the site, because the pipeline genuinely is an ordered sequence where order carries meaning: a track cannot be mastered before it is cleared. Do not use numbering anywhere else on the site. It is a structural claim about sequence, not a decoration.

**The eyebrow labels** (`PROBLEM`, `SOLUTION`, `MARKET`) carry over from the deck in mono, gradient-tinted, uppercase. They give a reader who is skimming a spine to hold onto.

---

# PART 3: THE SIGNATURE. THE 3D SCENE.

This is the one thing the site is remembered by. It gets all the boldness in the budget. Everything else stays quiet.

## 3.1 The idea: one continuous field

**Concept: The Catalog.**

The waveform arc in your logo, extruded into three dimensions and multiplied into a field of thousands of vertical bars in space. Each bar is one recording. The camera flies through this field for the entire length of the page. There is exactly one 3D scene, one camera path, and it never cuts.

The field reorganizes as you scroll, and each reorganization is a plot point:

**Act 1, The Noise** (hero)
Thousands of grey bars drifting in loose, unstructured space. No alignment, no color, slow ambient drift. Depth fog swallows the far ones. This is the unlicensed internet: everything exists, nothing is documented, no one knows who owns what.

**Act 2, The Reckoning** (problem)
The camera pulls back to reveal how vast the field is. Scattered bars flicker and go dark. Still monochrome. Nothing turns red, no warning colors, no alarm design. The restraint is the point: this reads as an industry realizing something quietly rather than a crisis graphic.

**Act 3, The Gate** (the money shot)
The camera turns to face a single vertical plane of cyan light stretching to the horizon. The bar field flows *through* it. Bars that pass through are ignited with the gradient, moving from grey to purple to blue. Bars that fail dissolve and fall away. The gate is the fingerprint scan, made literal.

This is the shot. Everything before it is setup, everything after is consequence. It should occupy a full viewport and hold for a beat before the page moves on. If a visitor screenshots one thing, this is it.

**Act 4, The Catalog** (solution)
The surviving gradient-lit bars snap from chaos into a precise ordered lattice. A grid, rotating slowly, indexed. Order out of noise. The camera orbits it.

**Act 5, The Split** (what buyers get)
The camera pushes into a single bar. It separates into four along the depth axis: vocals, drums, bass, other. Four labels in mono. This animates the stem product without a diagram.

**Act 6, The Arc** (close)
The camera pulls all the way back. The field compresses and resolves into the exact curve of the arc beneath your logo. The site ends inside its own logomark.

## 3.2 Why this works technically

The entire scene is **one `THREE.InstancedMesh`** of a single box geometry, with per-instance attributes for position, scale, color state, and clearance status, driven by a custom shader.

Everything above is not six scenes. It is one buffer of instance data and one uniform, `uProgress`, running 0 to 1, that morphs instance positions between named layout targets. That means:

- One WebGL context for the whole site
- One draw call for 20,000 bars
- Scroll position maps directly to `uProgress`, so it scrubs perfectly forwards and backwards
- No timers, no animation state to desync, no jank mismatch between scroll and motion

This is the single most important architectural decision in the build. Six separate canvases would be four times the work and would perform badly. Reject any implementation that creates a canvas per section.

## 3.3 Motion rules

- **The 3D scene animates only on scroll progress.** Never on a timer. The one exception is a very slow ambient drift on the hero before the user scrolls, so the page is not dead on arrival.
- **DOM elements animate on entry only.** Fade and 16px rise, 600ms, `cubic-bezier(0.16, 1, 0.3, 1)`. Once. They do not re-animate on scroll back up.
- **Hover states are 150ms.** Fast enough to feel like hardware.
- **Nothing bounces, nothing springs, nothing rotates on hover.** Playful motion undercuts the entire positioning.

## 3.4 Accessibility and fallback, non-negotiable

- `prefers-reduced-motion: reduce`: the canvas renders a single static frame of Act 4 (the ordered lattice, which is the most attractive still) and never updates. All DOM animation becomes instant.
- **Capability probe on load**: check `navigator.hardwareConcurrency`, `navigator.deviceMemory`, and WebGL renderer string. Below threshold, skip the canvas entirely and render a static gradient poster image.
- **FPS guard**: measure frame time for the first 2 seconds. Below 30fps sustained, drop instance count by half. Still below, swap to the poster.
- Every interactive element has a visible cyan focus ring. Focus is never removed, only restyled.
- The 3D canvas is `aria-hidden="true"`. It carries no information that is not also in text.

---

# PART 4: SCROLL AND STORYTELLING FLOW

## 4.1 Page map

```
┌──────────────────────────────────────────────────────┐
│  HERO                                    [Act 1]     │
│  Sticky nav, minimal: logo, "Platforms", "Artists"   │
│                                                       │
│  EMERGING-FIRST.                                      │
│  FULLY LICENSED.                                      │
│  AI-READY.                                            │
│                                                       │
│  The curated music catalog built for AI platforms     │
│  and enterprise buyers.                               │
│                                                       │
│  ┌─────────────────┐  ┌─────────────────┐            │
│  │ I license music │  │ I make music    │            │
│  │        →        │  │        →        │            │
│  └─────────────────┘  └─────────────────┘            │
│                                                       │
│              [ambient bar field drifting]             │
└──────────────────────────────────────────────────────┘
```

The fork is the hero's only call to action. No "Learn more." Two doors, both specific, both in the visitor's own words. Clicking either scrolls to the relevant deep section and sets a persistent path state that changes the copy in shared sections downstream.

```
┌──────────────────────────────────────────────────────┐
│  THE RECKONING                           [Act 2]     │
│  Mono eyebrow: WHAT ALREADY HAPPENED                  │
│                                                       │
│  $500M   RIAA suits against Suno and Udio, 2024      │
│  2 of 3  majors now license AI platforms             │
│  $0.005  per generation, the settlement template      │
│  0       independent artist seats at that table       │
│                                                       │
│  Numbers in mono, gradient. Labels in DM Sans dim.    │
│  Each row reveals on scroll, staggered 80ms.          │
└──────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│  THE GATE                                [Act 3]     │
│  Full viewport. Almost no copy.                       │
│                                                       │
│               Every track passes                      │
│               through the gate.                       │
│                                                       │
│  [the shot: field flowing through cyan plane,         │
│   grey going to gradient, failures falling away]      │
│                                                       │
│  Beneath, in mono, small:                             │
│  CLEARED · NEEDS DOCS · CONFLICT                      │
└──────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│  THE PIPELINE                            [Act 4]     │
│  01 Upload  02 Gate  03 Verify  04 Enhance  05 Catalog│
│  Horizontal, hairline-connected, gradient dots.       │
│  Numbering justified: this is a real sequence.        │
└──────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│  THE FORK RESOLVES                       [Act 5]     │
│  Two columns, but the one matching the visitor's      │
│  chosen path is expanded and lit; the other is        │
│  collapsed to a single line they can click.           │
│                                                       │
│  FOR PLATFORMS          │  FOR ARTISTS                │
│  Verified clearance     │  Mastering and stems, free  │
│  Mastered audio + stems │  You keep ownership         │
│  Structured metadata    │  Non-exclusive, always      │
│  One agreement          │  Founding Partner status    │
└──────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│  THE CATEGORY                                         │
│  Epidemic proved curation scales.                     │
│  The majors proved AI pays.                           │
│  oVoxi is the first catalog built for both.           │
└──────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│  CLOSE                                   [Act 6]     │
│  Field resolves into the logo arc.                    │
│  One CTA, matched to path.                            │
│  Footer: contact, legal, nothing else.                │
└──────────────────────────────────────────────────────┘
```

## 4.2 Copy principles

- Sentence case everywhere except mono labels.
- No exclamation marks. No "revolutionize," "unlock," "empower," "seamless," "cutting-edge."
- Buttons say what happens: "Start an application," not "Get started." "Request a sample pack," not "Contact us."
- The button label and the resulting page heading match. "Request a sample pack" leads to a page headed "Request a sample pack."
- Every number on the page is real and sourced. If it cannot be sourced, it does not go on the page.

---

# PART 5: TECH STACK

Constrained by the decision to build in place in the existing CRA/CRACO app.

| Layer | Choice | Why this one |
|---|---|---|
| Framework | **Existing CRA + CRACO** | Your call. Zero migration risk to Clerk auth and the working app routes. |
| 3D | **@react-three/fiber + @react-three/drei** | Declarative three.js in React. Works in CRA without config changes. |
| three.js | **three (pinned exact version)** | Pin it. R3F is version-sensitive and a minor bump can break drei. |
| Scroll | **Lenis** | Smooth scroll normalization. Small, no dependencies, plays well with GSAP. |
| Scroll timeline | **GSAP + ScrollTrigger** | The scrub-linked timeline that drives `uProgress`. The only tool that does scrubbing reliably. |
| DOM animation | **Framer Motion** | Entry reveals only. Already React-idiomatic. |
| Styling | **Tailwind (already installed)** | Extend the theme with the tokens above. No new CSS system. |
| Prerender | **react-snap** (build step) | Solves the crawler and link-preview problem without leaving CRA. Runs after build, writes static HTML per route. |
| Fonts | **Self-hosted woff2** | Syne, DM Sans, JetBrains Mono. Self-host, do not use Google Fonts CDN. Removes a render-blocking third party and a GDPR question. |

**Rejected, and why:**
- **Next.js migration**: correct long term, rejected per your call. Revisit if the prerender step proves insufficient.
- **Spline or a hosted 3D tool**: locks the signature element to a vendor. You just lived through that with Lalal.
- **Video background instead of WebGL**: cheaper, but not scrubbable, and a 20MB video is worse for load than a shader.
- **Post-processing bloom**: tempting on a gradient scene, and it doubles GPU cost. Skip on v1, evaluate later, never on mobile.

## 5.1 Performance budget, enforced

| Metric | Target | How |
|---|---|---|
| LCP | under 2.5s | Hero text is static HTML via prerender. Canvas fades in over a gradient poster. |
| 3D bundle | lazy, not in main chunk | `React.lazy` + `Suspense`. App routes must never download three.js. |
| Instance count | 20k desktop / 6k mobile | Adaptive at init. |
| Total blocking time | under 200ms | Shader compile happens off the critical path. |

That third row is the one that protects your existing app. If three.js ends up in the main bundle, `/vault` and `/admin` get slower for artists who will never see the marketing site. Verify this after the first build.

---

# PART 6: BUILD ORDER

Eight phases. Each one ships independently, each one is revertible, and the site is never broken between them because the new work is behind a feature flag until Phase 8.

| Phase | What | Ships? | Risk |
|---|---|---|---|
| **0** | Safety rails: branch, flag, route isolation | No | None |
| **1** | Design tokens + fonts into Tailwind config | No | None |
| **2** | Static marketing page, full copy, zero 3D | Yes, behind flag | Low |
| **3** | Lenis + GSAP scroll scaffolding, DOM reveals | Yes | Low |
| **4** | Canvas mount, InstancedMesh, Act 1 only | Yes | Medium |
| **5** | Acts 2 through 6, the full morph sequence | Yes | Medium |
| **6** | The Gate shader, the signature shot | Yes | Medium |
| **7** | Fallbacks, reduced motion, capability probe, perf | Yes | Low |
| **8** | Prerender step, flag removed, cut over | Yes, live | Medium |

**Phase 2 is the checkpoint that matters.** A fully written, well-typeset, zero-3D marketing page is already better than what you have today. If you run out of time or budget, you stop at Phase 3 and you have shipped something good. The 3D is an enhancement layer on top of a page that works without it. Build in that order and you can never end up with a half-finished 3D site.

---

# PART 7: CLAUDE CODE IMPLEMENTATION

## 7.1 Rules that apply to every single prompt

Paste this block at the top of each session. These come from your own repeated failure modes.

```
STANDING RULES FOR THIS REPO:

1. Before editing anything: git pull. Divergent branches from parallel
   sessions have broken this repo before.
2. Show me every change before saving it. Do not save and then explain.
3. Never modify frontend/src/index.js. The Clerk publishable key is
   hardcoded there deliberately because CRACO env var injection fails.
   Touching it breaks auth in production.
4. Never modify anything under the /apply, /vault, or /admin routes or
   their components. Those are live and working.
5. All new marketing code lives in frontend/src/marketing/. Nothing new
   goes in the existing component directories.
6. After any frontend change, deploy with: npx vercel --prod
   git push alone does NOT deploy. Vercel GitHub auto-deploy is broken
   on this project. Confirmed, not a guess.
7. Commit and push to the feature branch after each approved change.
8. NO EM DASHES in any copy you write. Use commas, colons, or periods.
```

## 7.2 Phase 0: Safety rails

**What this does in plain terms:** builds a wall around the new work so it cannot touch anything that currently works, and gives you an off switch.

**Prompt:**

```
Set up isolation for a new marketing site build in this repo.

1. Create and check out a branch: feat/marketing-revamp

2. Create the directory frontend/src/marketing/ with subfolders:
   sections/, three/, hooks/, styles/

3. In frontend/src/App.js (or wherever routes are defined), add a
   feature flag. Read REACT_APP_NEW_MARKETING from the environment,
   defaulting to false. When true, the "/" route renders the new
   marketing page. When false, it renders exactly what it renders today.
   Do not change any other route.

4. Create frontend/src/marketing/MarketingPage.jsx as a placeholder
   that renders a black div with the text "new marketing".

Show me the diff for App.js before saving. Then confirm the existing
site still renders identically with the flag off.
```

**How you verify it worked:** run the site locally with the flag off. Everything looks exactly as it does now. Turn the flag on, you see a black screen with two words. That is success.

## 7.3 Phase 1: Design tokens

**In plain terms:** teach Tailwind your brand colors and fonts so every later prompt can just say "use the gradient" instead of pasting hex codes.

**Prompt:**

```
Add the oVoxi design system to Tailwind.

1. Download and self-host these fonts as woff2 in frontend/public/fonts/:
   - Syne 800
   - DM Sans 300 and 400
   - JetBrains Mono 400
   Add @font-face rules with font-display: swap in the global stylesheet.

2. Extend tailwind.config.js theme (extend only, do not replace) with:

   colors:
     ovx.void: '#000000'
     ovx.g1: '#B44FD4'
     ovx.g2: '#7B5EA7'
     ovx.g3: '#6B7FD4'
     ovx.cyan: '#4FC3F7'
     ovx.surface: '#0A0A0C'
     ovx.line: '#1C1C21'
     ovx.dim: '#8A8A94'
     ovx.faint: '#4A4A52'

   fontFamily:
     display: Syne
     body: 'DM Sans'
     mono: 'JetBrains Mono'

   backgroundImage:
     'ovx-gradient': 'linear-gradient(135deg, #B44FD4 0%, #7B5EA7 50%, #6B7FD4 100%)'

3. Add a fluid type scale using clamp() as CSS custom properties in the
   global stylesheet: --fs-hero, --fs-h1, --fs-h2, --fs-lead, --fs-body,
   --fs-label, --fs-data. Use the values I will paste next.

Show me tailwind.config.js before saving. Confirm no existing color or
font names were overwritten.
```

Then paste the type scale from section 2.2 of this document.

**Verify:** existing pages look completely unchanged. You have only added, never replaced.

## 7.4 Phase 2: The static page

**In plain terms:** build the whole website with real words and real layout, and no 3D at all. This is the phase that matters most. Take your time here.

Break this into one prompt per section rather than one giant prompt. Claude Code produces better work on a bounded section than on a whole page.

**Prompt template, repeat per section:**

```
Build the [SECTION NAME] section of the new marketing page.

File: frontend/src/marketing/sections/[Name].jsx

Design constraints:
- Background: pure black (ovx.void). No section has its own background
  color. The whole page is one black surface.
- Headings: font-display (Syne 800), letter-spacing -0.02em,
  line-height 0.95
- Eyebrow labels: font-mono, uppercase, tracking 0.12em, text-[13px],
  colored with the gradient via bg-clip-text
- Body: font-body at 400 weight below 20px, 300 weight above
- Any number, percentage, or status value: font-mono
- The gradient is ONLY used on things that represent a verified or
  cleared state. Never as decoration.
- Cyan is ONLY used on interactive elements. Nothing cyan is static.
- Vertical padding: 160px desktop, 96px mobile
- Max content width 1440px, 120px side gutters desktop, 24px mobile

Content: [paste the copy from the blueprint]

No animation in this phase. Static only. Fully responsive down to 375px.
Every interactive element needs a visible cyan focus ring.

Show me the component before saving.
```

**Verify after each section:** open at 375px wide and at 1920px. Read every line of copy out loud. If a sentence sounds like a press release, rewrite it before moving on.

## 7.5 Phase 3: Scroll system

**In plain terms:** make scrolling feel smooth and heavy instead of jumpy, and make things fade in as you reach them.

**Prompt:**

```
Add the scroll system to the marketing page only.

1. Install: lenis, gsap, framer-motion
   Pin exact versions in package.json. No carets.

2. Create frontend/src/marketing/hooks/useLenis.js. It initialises Lenis
   with lerp 0.1, wraps it in a React effect, and destroys it on unmount.
   Critical: it must ONLY run on the marketing page. If Lenis is active
   on /vault or /admin it will interfere with those pages. Mount it
   inside MarketingPage, never in App.

3. Register ScrollTrigger with GSAP and connect it to Lenis using
   ScrollTrigger.scrollerProxy so the two stay in sync.

4. Create frontend/src/marketing/hooks/useScrollProgress.js. It returns
   a normalized 0 to 1 value representing progress through the entire
   marketing page, driven by a scrubbed ScrollTrigger. This single value
   will later drive the whole 3D scene. Expose it via React context so
   any component can read it without prop drilling.

5. Create a <Reveal> wrapper component using Framer Motion:
   fade 0 to 1 and translateY 16px to 0, duration 600ms,
   easing cubic-bezier(0.16, 1, 0.3, 1), triggered once at 20% viewport
   entry. It must NOT re-animate on scroll back up.

6. Wrap the content blocks in each section with <Reveal>. Stagger
   sibling items by 80ms.

7. If prefers-reduced-motion is set: disable Lenis entirely, and make
   Reveal render children with no animation.

Show me useScrollProgress.js and the Lenis mounting code before saving.
```

**Verify:** scroll the marketing page, it should feel weighted. Then go to `/vault` and scroll. It must feel completely normal. If `/vault` scrolling changed, Lenis leaked out of the marketing page and must be fixed before continuing.

## 7.6 Phase 4: The canvas and the field

**In plain terms:** put a 3D window on the page and fill it with thousands of floating bars. No story yet, just the raw material.

**Prompt:**

```
Add the 3D scene foundation to the marketing page.

1. Install: three (pin the exact version), @react-three/fiber,
   @react-three/drei. Pin all three exactly.

2. CRITICAL: the 3D code must be lazy loaded. Create
   frontend/src/marketing/three/Scene.jsx and import it in MarketingPage
   with React.lazy inside a Suspense boundary. three.js must not appear
   in the main JS bundle. After building, run a bundle analysis and show
   me that three.js is in a separate chunk. If it is in the main chunk,
   stop and fix it before continuing. Artists loading /vault must never
   download three.js.

3. The canvas is fixed position, full viewport, z-index behind all page
   content, pointer-events none, aria-hidden true. Page content scrolls
   over it.

4. Build the bar field as a SINGLE THREE.InstancedMesh:
   - Geometry: BoxGeometry(1, 1, 1), reused for every instance
   - Instance count: 20000 on desktop, 6000 if the viewport is under
     768px wide
   - Per-instance attributes: aTargetA (vec3), aTargetB (vec3),
     aSeed (float), aCleared (float)
   - Custom ShaderMaterial with a uniform uProgress (float)

5. For now, populate aTargetA with the "noise" layout: random positions
   in a box 200 wide, 60 tall, 400 deep, with random Y scales between
   0.5 and 8, all with aCleared = 0. Set aTargetB identical to aTargetA.

6. The vertex shader mixes between aTargetA and aTargetB using
   uProgress. The fragment shader colors bars grey (#8A8A94) when
   aCleared is 0 and applies the purple to blue gradient when aCleared
   is 1, mixed by aCleared.

7. Add exponential fog matching the black background so distant bars
   fade out.

8. Add a very slow ambient drift using a sine function on aSeed, so the
   field is alive before the user scrolls.

9. Camera: perspective, fov 50, positioned to look into the field.

Show me the shader code and the instance setup before saving.
Do not connect scroll yet.
```

**Verify:** you should see a slowly drifting field of grey bars behind your text. Check the browser dev tools Network tab: three.js should load as its own chunk, and it should not load at all when you visit `/vault`.

## 7.7 Phase 5: The six acts

**In plain terms:** connect the scrollbar to the 3D scene, so scrolling moves the bars between six arrangements.

**Prompt:**

```
Connect the scroll progress to the 3D scene and build the act sequence.

1. Read the scroll progress context value from Phase 3 and feed it into
   the uProgress uniform every frame via useFrame. Do not use React
   state for this. Writing to a uniform ref directly avoids re-rendering
   the whole tree 60 times per second.

2. Define six named layouts as functions that generate instance
   positions, scales, and cleared flags for the full instance count:

   ACT_1_NOISE     random scatter, wide and deep, all cleared = 0
   ACT_2_EXPANSE   same scatter but camera-relative wider spread,
                   15% of instances scaled to zero (going dark)
   ACT_3_GATE      instances arranged in a stream flowing along +Z
                   through the plane at z = 0; instances with
                   aSeed > 0.25 get cleared = 1, the rest scale to zero
                   as they cross
   ACT_4_LATTICE   precise grid, 100 x 20 x 10, even spacing,
                   all surviving instances cleared = 1
   ACT_5_STEMS     all instances collapse toward the center except
                   four columns separated along Z
   ACT_6_ARC       instances form the curve of the oVoxi logo arc

3. Map scroll progress 0 to 1 across these six acts with a GSAP timeline.
   On each act transition, copy the current aTargetB into aTargetA and
   write the next layout into aTargetB, then reset the local mix value.
   This is how one shader morphs through six states.

4. Animate the camera along a CatmullRomCurve3 path through the field,
   with the same scroll progress driving position along the curve. The
   camera must be facing the gate plane head-on during act 3.

5. Every act transition uses easing power2.inOut, except the entry into
   act 3 which uses power3.out so the gate arrives with weight.

Show me the layout generator functions and the timeline mapping before
saving. Build one act at a time and let me check each before you move to
the next.
```

That last line matters. Do not let it build all six at once.

**Verify:** scroll slowly from top to bottom, then back up. The motion should reverse perfectly. Any pop, jump, or state that does not reverse is a bug in the target-swapping logic.

## 7.8 Phase 6: The Gate

**In plain terms:** build the one shot the whole site is designed around. Make it look expensive.

**Prompt:**

```
Build the Gate: the signature visual moment of the site.

At act 3, add a vertical plane at z = 0 spanning the full width and
height of the visible field.

1. The plane uses a custom shader: mostly transparent, with a bright
   cyan (#4FC3F7) emissive core that falls off softly toward the edges.
   Subtle vertical scan-line movement, slow, no more than 0.2 units per
   second. It should read as a scanner, not a laser show.

2. In the bar field vertex shader, add a uniform uGatePlaneZ. For each
   instance, compute its distance to the gate plane. Within 8 units of
   the plane, drive the ignition:
   - Approaching (z < 0): bar is grey
   - At the plane: brief cyan flash, one frame equivalent
   - Departing (z > 0): if aCleared is 1, lerp from cyan into the
     purple-to-blue gradient over 12 units of travel. If aCleared is 0,
     lerp scale to zero and fall away on Y.

3. Add a soft additive glow to ignited bars in the fragment shader.
   Do NOT use a post-processing bloom pass. It costs too much on
   mid-range hardware. Fake it in the fragment shader.

4. The gate section is a full viewport sticky section so the moment
   holds. Scroll progress within that sticky section drives the flow
   speed of instances through the plane.

Show me the gate shader and the ignition logic before saving.
```

**Verify:** this should stop you when you scroll to it. If it does not, the problem is usually that it goes by too fast. Lengthen the sticky section before adjusting the shader.

## 7.9 Phase 7: Fallbacks and performance

**In plain terms:** make sure the site does not melt someone's laptop or exclude someone who gets motion sickness.

**Prompt:**

```
Add capability detection and fallbacks to the 3D scene.

1. Create frontend/src/marketing/hooks/useCanRender3D.js. Before mounting
   the canvas, check:
   - prefers-reduced-motion: reduce  ->  do not mount canvas
   - navigator.hardwareConcurrency < 4  ->  do not mount canvas
   - navigator.deviceMemory < 4 (when available)  ->  do not mount
   - WebGL context creation fails  ->  do not mount
   - WEBGL_debug_renderer_info reports SwiftShader or a software
     renderer  ->  do not mount

2. When the canvas does not mount, render a static poster image in its
   place: a high-quality PNG export of the act 4 lattice on black.
   Generate this by screenshotting the running scene at act 4 and saving
   it to frontend/public/. It should be under 200KB as a webp with a
   PNG fallback.

3. Add an FPS guard. Measure average frame time over the first 2 seconds
   after mount. If under 30fps, halve the instance count. Re-measure. If
   still under 30fps, unmount the canvas and show the poster.

4. Under prefers-reduced-motion specifically, if the canvas is skipped,
   also confirm all DOM reveals are instant and Lenis is off.

5. Audit focus states across the whole marketing page. Every link and
   button gets a 2px cyan focus ring with 2px offset, visible on black.

6. Run Lighthouse on the marketing page and show me the report. Targets:
   LCP under 2.5s, TBT under 200ms, accessibility score 100.

Show me useCanRender3D.js before saving.
```

## 7.10 Phase 8: Prerender and cut over

**In plain terms:** make the site show up properly when someone pastes the link into Slack or an email, then turn the new site on for real.

**Prompt:**

```
Add prerendering and cut the new marketing page over to production.

1. Install react-snap. Add a postbuild script in package.json that runs
   react-snap after the CRA build.

2. Configure react-snap to prerender ONLY the marketing routes. It must
   not attempt to prerender /vault, /apply, or /admin, because those
   require Clerk auth and prerendering them will either fail or leak an
   authenticated shell into static HTML. List the safe routes
   explicitly.

3. Add proper meta tags to the marketing page: title, description,
   og:title, og:description, og:image, twitter:card set to
   summary_large_image. The og:image should be a 1200x630 PNG using the
   act 4 lattice with the logo and the three-line positioning statement.

4. Build locally and show me the generated static HTML for "/". Confirm
   the hero headline text is present in the raw HTML, not just in the
   JS bundle. This is the whole point of this phase.

5. Verify Clerk still initialises correctly on /vault after the
   prerender step. This is the highest risk moment in the entire build.
   Test signing in and out.

6. Only after all the above passes: set REACT_APP_NEW_MARKETING to true
   in the Vercel project environment variables, merge
   feat/marketing-revamp into main, push, and then deploy manually with
   npx vercel --prod

7. Confirm the deployment timestamp in the Vercel dashboard updated
   before testing anything.
```

**Verify:** open the live site in an incognito window. Then paste `ovoxi.net` into Slack or a draft email and confirm the preview card renders with the image and headline. Then sign in to `/vault` and confirm auth still works. That last check is the one that matters most, because a broken Clerk is a broken product.

---

# PART 8: WHAT I NEED FROM YOU

Before Phase 2, I need decisions on:

1. **The restraint bet** in section 1.2. If you want density and proof-logos instead, say so now, it changes the whole design.
2. **Final hero copy.** I have used the deck's three-line positioning. Confirm or replace.
3. **The two fork labels.** I have written "I license music" and "I make music." These are the two most important words on the site.
4. **Whether investors get a third door.** My recommendation is no. Send them a direct link to a `/investors` route that is not in the nav.

And two things I flagged and still need answers on:

5. The stem pipeline stopgap, whenever you are ready.
6. Whether the deck's "live in production" claim gets softened while stems are down.
