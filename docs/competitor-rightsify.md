# Competitive Intelligence: Rightsify / GCX

Compiled 2026-08-26. Every claim below is sourced. Where the record is silent it says
"not found" — those gaps are findings in themselves, not omissions.

---

## 0. Two corrections to what we believed going in

**1. Yamaha Music Innovations is Rightsify's CUSTOMER, not its investor.**

Yamaha's own fund site lists Rightsify under **"Business Partnerships"**, explicitly
separate from its portfolio. The actual YMIF portfolio is Songboy, Freebeat, CommonTime
Pathways, Offside, Mogul, Meld Studio, Nero, TONE3000 — Rightsify is not among them.
Yamaha's June 2025 release describes a procurement relationship: partnership began May
2025, implementing division "Research & Development", activity "purchasing music data that
has already undergone the licensing process."

CB Insights lists Yamaha as a "Known Investor" with a blank amount and no date on an
unclaimed profile — almost certainly an aggregator auto-ingesting the partnership press
release and mis-typing it. Do not repeat the investment claim.

**Why this matters more than the correction:** YMIF's portfolio is *open* in this
category, and Yamaha has already demonstrated it will pay for licensed music data. They
are a validated buyer, not a conflicted investor.

**2. Rightsify has never raised venture capital.** Bootstrapped, reportedly profitable,
~24 FTE plus ~76 annotation contractors. No board, no institutional investors, no named
CTO or second executive anywhere in the public record. Founder Alex Bestall, sole founder,
company founded 2013. His pre-2013 background is entirely undocumented publicly.

---

## 1. What they actually do

Three current products. A fourth was quietly killed.

| Product | What it is | Price |
|---|---|---|
| **GCX** (Global Copyright Exchange) | Human-created "copyright-cleared" music datasets for AI training | No public rate card; Datarade lists **from $10,000/year** |
| **Gramosynth** | *Synthetic* music dataset generation for AI labs — the new flagship | Not published |
| **BGM** | AI-generated background music for venues | **$99 per location per year** |
| ~~**Hydra / Hydra II**~~ | Text-to-music generative model | **Retired. See §4.** |

Origin story, from the founder: Rightsify spent eleven years as a conventional sync and
background-music library serving hotels, airports and airlines. Those clients needed
24-hour playlists, which forced years of manual tagging — key, tempo, chords,
instrumentation. During COVID a major tech company asked to license the tagged data for AI
training. Rightsify initially refused, then reconsidered. Dataset licensing is now its
primary revenue source. In Bestall's words, they "accidentally built the most
comprehensive music dataset."

Catalog is ~95% instrumental, claimed 800+ instruments, with deliberate investment in
non-Western repertoire (Indian, Thai) under the "Global Harmonies" banner.

---

## 2. What each participant receives — the finding that matters most

### Composers: a work-for-hire buyout. No ongoing share. Nothing.

GCX's own FAQ, verbatim:

> "Yes, all GCX datasets are wholly owned by Rightsify and affiliated parties via
> **work for hire agreements**."

Corroborated independently — LA Business Journal: *"Rightsify purchases rights to music
from artists outright."*

Work-for-hire under US law makes Rightsify the **author** of record. The composer keeps no
copyright, has no reversion, and has **no statutory termination right** — works made for
hire are excluded from 17 U.S.C. §203. No royalty or revenue share attaches anywhere in
any document found.

**No composer rate has ever been published. No composer agreement is public.** Searches of
MusicLibraryReport, Reddit, VI-Control and Gearspace turned up **no firsthand accounts at
all** — the only Rightsify thread on MusicLibraryReport is from April 2017, pre-AI, with
two replies.

### The rhetorical move worth understanding

Bestall is a vocal advocate for creator opt-in. From the MusicWorks interview:

> "if you're a marketplace with a lot of contributors and you just go and licence that
> whole dataset to a company without contributors opting in, we disagree with that.
> **We think creators should have the opt-in.**"

Read that carefully. "Opt-in" is applied to *marketplaces that aggregate third-party
contributors* — a model Rightsify does not use, because it owns its catalog outright. A
company that bought its catalog via work-for-hire satisfies every opt-in principle with
**zero consent events and zero creator payments**, because there is nobody left with
anything to consent to.

Fairly Trained certification does not close this gap either: its own FAQ states fair
compensation is an improvement that "flows from consent" but is **not a requirement**.
Rightsify is certified at company level; Hydra is not individually listed.

### A structural discontinuity nobody has examined

Before the AI pivot, Rightsify ran a **non-exclusive artist program** on the opposite
terms. From a March 2018 announcement: *"Rightsify is non-exclusive and artists keep 100
percent ownership of their rights."* Roughly 300+ artist members, 10,000+ songs, paid
monthly on tracked plays.

So two mutually exclusive populations exist. GCX's position is that datasets contain only
the wholly-owned work-for-hire material.

**Unverified either way, and worth knowing:** whether any pre-2023 non-exclusive artist's
tracks ever entered a GCX dataset; whether pre-2023 work-for-hire agreements contained
express AI/machine-learning language; whether any artist was notified of the pivot. No
allegation, no denial, no document. **Do not assert wrongdoing** — but note that a
composer signing a buyout in 2016 could not have priced AI training into it.

### AI buyers: a contradiction in the paperwork

Marketing says *"all dataset licenses come with full indemnification."*
GCX's actual Terms of Service run the indemnity **the other way**: users must indemnify
GCX; liability capped at fees paid; service "as is," no warranties.

For a company whose entire value proposition is legal safety, **there is no published
dataset licence agreement at all** — `gcx.co/terms` 404s. That is the single largest gap
in the record.

Deal shapes, per Bestall: flat fee for stem-separation and recommendation use cases;
flat fee, revenue share, or hybrid for generative training.

### Sector benchmark

Almost nobody publishes creator payout terms. ProRata's 50/50 split is the only hard
number in the adjacent space, and it's news, not music. Sureel, Musical AI and Beatoven
all claim per-output attribution payouts and disclose no percentages.

---

## 3. Vision

- Positioning: *"we have positioned ourselves solidly at the data layer of AI."*
- On the opportunity: AI is *"a whole new distribution method"* — potentially *"bigger than streaming."*
- On the industry's hostility: *"it's better to have a seat at the table rather than sit on the sidelines… For us, it's really about how to survive long-term as a business."*
- Serial pivot as identity: *"11 years ago we started in sync, 9 years ago in background music licensing and now we are an AI data company."*

**No 5-year plan document, podcast appearance, keynote or op-ed from 2025 or 2026 was
found anywhere.**

### The Dataset Providers Alliance

Founded June 2024, seven members. **Two of the seven are Bestall's own companies**
(Rightsify and GCX), his is the lead quote on both the launch and the position paper, and
the DPA site names no chair or governance structure.

Its platform — opt-in only, bilateral private deals, **explicit opposition to
government-mandated collective licensing** — maps precisely onto the commercial interest
of a dataset broker.

It has **no major-label members, no AI-lab members, and no rightsholder members**. Its blog
last posted December 2024; its last event was a January 2025 webinar. Nobody has publicly
criticised the governance overlap, which is itself a signal about how visible the DPA is.

---

## 4. Weaknesses

### Hydra was retired without announcement

`rightsify.com/hydra` now serves the Gramosynth page with no mention of Hydra. It is gone
from the homepage nav. Wayback confirms it was live in February 2025. **No press release,
no blog post, no trade coverage, no stated reason.** A third-party directory noted the
change in July 2026.

Plausible reading (analysis, not fact): a $39–$99/month prosumer generator was never
competitive with Suno or Udio, and it put Rightsify in direct competition with the AI labs
that are supposed to be its dataset customers.

### The company went quiet after mid-2024

| Channel | Last activity |
|---|---|
| GCX blog | May 2024 |
| Rightsify blog | Nov 2025 — and it's a *background music* post |
| Press releases | All 2023–2024 |
| DPA blog | Dec 2024 |
| Trade coverage (MBW, Music Ally, Billboard, DMN) | **Nothing found in 2025–2026** |

**Music Business Worldwide has never covered Rightsify at all.** Hacker News has zero
mentions. The Atlantic's June 2026 investigation into AI music data provenance — the
defining story in this space — does not name them.

### Numbers that don't reconcile

| Claim | Figure | When |
|---|---|---|
| GCX launch | 4.4 million hours | Aug 2023 |
| Current homepage | 1 million+ hours, 12M+ songs | Now |
| Metadata parameters | "400+" vs "800+" | Two different releases |

The hours figure went **down 77%**. "32 billion parameters" was used to describe a
*dataset*, which is incoherent. No independent verification of any scale claim exists.

### Other

- **One named customer, ever: Yamaha.** In July 2024 Bestall said announcements were coming "in the next few months." Two years later, GCX still says only "leading AI companies."
- **An open-source promise reported by LABJ was never fulfilled.**
- **A strategic reversal, unexplained.** In 2024: *"What AI companies want is human data, not AI-generated data. They want it to be ground truth"* and *"you can't feed AI models entirely AI music."* The 2026 flagship product is a synthetic data generator.
- **Pricing signal is small.** ~$10k/year list is not in the same conversation as the eight-figure direct label deals.
- **Clearance is catalog-level, not per-asset.** Their public warranty is a blanket "all copyrights are owned by GCX or affiliated parties" — not per-track chain of title on both the recording and composition sides.

---

## 5. The market is moving away from their position

Direct licensing has taken over. ~274 commercial AI licensing agreements across creative
sectors as of early 2026 (WPI Economics for the BPI). Named counterparties are Suno, Udio,
ElevenLabs, Splice — **all direct-to-rightsholder, none via dataset brokers.**

- Nov 2025: **KLAY licensed by all three majors** — first AI company to achieve it
- Oct/Nov 2025: **UMG+Udio, WMG+Suno, WMG+Udio** settlements with licensed-model commitments
- Jan 2026: **Cloudflare acquires Human Native AI**
- Jun 2026: **Warner Music acquires Sureel AI** (attribution)
- Feb 2025: **Vermillio raises $16M led by Sony Music**
- Jan 2026: **Musical AI raises $4.5M** for attribution infrastructure

The middleman layer is being **acquired or bypassed**. Capital is flowing to
attribution and provenance infrastructure, not to raw corpora.

**The long tail remains untouched:** only 16% of surveyed independent BPI members had
begun exploring AI licensing; 5% of small music companies had completed agreements.

---

## 6. What this means for oVoxi

### The wedge is creator economics, and it is wider than we assumed

Rightsify's model is: **buy the copyright outright, keep 100% of the AI upside forever.**
oVoxi's model is a revenue split with artists who retain ownership. That is not a
positioning difference, it is an opposite structure.

Their vulnerability is that "ethical" in their usage means **cleared title**, not **shared
upside** — and they have built an entire standards body around a definition of ethics that
their own composers cannot benefit from. That distinction is currently invisible to the
market because nobody has looked. It is available to whoever articulates it first.

**Caution:** do not overclaim. We do not know what they pay composers up front, and a
generous buyout is not automatically unfair. The defensible statement is structural:
under work-for-hire, the creator captures none of the AI upside, however large it becomes.

### Yamaha is a buyer, and buyers are what we lack

They pay for licensed music data today, from a vendor with one named customer and no
capital behind it. YMIF's portfolio has no dataset company in it. Both the commercial door
and the investment door are open, and they are separate doors.

### The market shift cuts both ways

Bad news: if AI labs increasingly license direct from majors, a rights intermediary is
squeezed — the same squeeze crushing Rightsify.

Good news: the squeeze is on **corpus vendors**. Capital is going to **attribution and
provenance infrastructure** — Sureel to Warner, Vermillio funded by Sony, Musical AI
funded, Human Native to Cloudflare. That is the layer oVoxi's rights policy engine and
provenance record occupy. And the independent long tail — 95% of small music companies
with no AI agreement — is exactly the market wedge already identified.

### The uncomfortable read

Every company acquired or funded in this space had **the thing we do not yet have**:
a signed counterparty. Sureel had STIM and Symphonic. Musical AI had Symphonic and
Beatoven. Rightsify, with no signed named customer beyond Yamaha, has gone quiet and been
passed over.

One AI company as a design partner is worth more than any amount of positioning.

---

## 7. Questions to put to them, or to a mutual contact

1. Were any tracks from the pre-2023 non-exclusive artist program ever included in a GCX dataset or a Hydra training run?
2. Do any work-for-hire agreements signed before January 2023 contain express AI/machine-learning language?
3. Does any composer receive a share of GCX dataset licensing revenue?
4. Why was Hydra retired?
5. Which indemnity governs a GCX dataset licence — the marketing promise or the ToS?

---

## Sources

**Company:** [rightsify.com](https://www.rightsify.com/) · [GCX](https://www.gcx.co/) · [GCX FAQ](https://www.gcx.co/faq) · [GCX ToS](https://www.gcx.co/terms-of-service) · [Rightsify ToS](https://www.rightsify.com/terms-of-service) · [Gramosynth](https://www.gramosynth.com/)

**Journalism:** [LA Business Journal](https://labusinessjournal.com/technology/ai/) · [MusicWorks — Bestall interview](https://musicworks.substack.com/p/data-licensing-and-the-future-of) · [Music Ally](https://musically.com/2024/03/21/rightsify-unveils-most-diverse-and-truly-ethical-ai-music-model/) · [Digital Music News — Hydra II](https://www.digitalmusicnews.com/2024/03/20/rightsify-releases-hydra-ii/) · [Pasadena Now — GCX launch](https://pasadenanow.com/main/pasadena-based-rightsify-launches-gcx-worlds-first-ai-music-dataset-licensing-service)

**Yamaha:** [Yamaha Music Innovations](https://yamahamusicinnovations.com/) · [Yamaha — Partners Up with Four Startups](https://usa.yamaha.com/news_events/2025/yamaha-music-innovations-partners-up-with-four-startup-companies.html) · [MBW — $50m fund](https://www.musicbusinessworldwide.com/yamaha-launches-50m-fund-to-power-music-and-media-startups/)

**Creator economics:** [BroadwayWorld 2018 artist program](https://www.broadwayworld.com/bwwmusic/article/Rightsify-Helps-Artists-Get-Paid-When-Their-Music-is-Played-In-Businesses-20180326) · [Fairly Trained FAQs](https://www.fairlytrained.org/faqs) · [Fairly Trained certified](https://www.fairlytrained.org/certified-models) · [PMA — Are You Training Your Replacement?](https://pmamusic.com/ai-training-licenses-are-you-training-your-replacement/) · [MusicLibraryReport thread](https://musiclibraryreport.com/forums/topic/rightsify-anybody-checked-them-out-comments/)

**DPA:** [DPA](https://www.thedpa.ai/) · [members](https://www.thedpa.ai/members) · [PRNewswire launch](https://www.prnewswire.com/news-releases/leading-dataset-licensors-unite-to-launch-the-dataset-providers-alliance-dpa-302182603.html) · [BigDATAwire position paper](https://www.bigdatawire.com/2024/09/06/dataset-providers-alliance-releases-extensive-position-paper-on-ai-data-licensing/)

**Market:** [MBW — KLAY/majors](https://www.musicbusinessworldwide.com/umg-sony-and-warner-strike-licensing-deals-with-new-ai-music-platform-klay/) · [MBW — WMG acquires Sureel](https://www.musicbusinessworldwide.com/warner-music-group-acquires-sureel-ai-the-attribution-startup-that-traces-how-ai-models-use-artists-work/) · [Cloudflare acquires Human Native](https://www.cloudflare.com/en-gb/press/press-releases/2026/cloudflare-strengthens-content-offering-to-ai-companies-with-acquisition-of-human-native/) · [MBW — Musical AI $4.5M](https://www.musicbusinessworldwide.com/musical-ai-bags-4-5m-in-funding-round-to-scale-ai-attribution-tech/) · [Businesswire — Vermillio $16M](https://www.businesswire.com/news/home/20250228026074/en/Vermillio-Completes-$16-Million-Series-A-Funding-Round-Led-by-Sony-Music-and-DNS-Capital) · [DMN — 274 AI licensing deals](https://www.digitalmusicnews.com/2026/06/22/ai-licensing-deals-stats-february-2026/) · [Troveo — licensed music training data](https://www.troveo.ai/resources/licensed-music-training-data)
