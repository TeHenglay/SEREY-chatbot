# Serey Landing Page Builder V2 — AI Training Reference

> **Source of truth**: All data below is extracted directly from the live V2 React components in `src/components/Shared/LandingPageV2/` and `src/components/LandingBuilderV2/LandingBuilderV2.js`.  
> **Purpose**: Train an AI backend to auto-suggest and generate landing page JSON for Serey community owners.

---

## 1. Architecture Overview

The V2 landing page is stored as a **JSON array of section objects** in the database. The builder (`LandingBuilderV2.js`, ~174KB) lets owners build the page visually. The output is saved via API and rendered by shared section components.

| Layer | Path |
|---|---|
| Builder UI | `src/components/LandingBuilderV2/LandingBuilderV2.js` |
| Section renderers | `src/components/Shared/LandingPageV2/*.js` |
| Page SCSS | `src/assets/scss/custom/_social-media-owner-landing.scss` |
| Page route | `/social-media-owners` → menu option "Build/Edit Landing Page" |
| API (GET) | `GET /api/v2/landing-pages?community_id={id}` |
| API (SAVE) | `POST /api/v2/landing-pages` body: `{ community_id, content: [...sections] }` |

---

## 2. Section Registry

### Core Sections (always present)
| Key | Type | Label | Default `is_hidden` |
|---|---|---|---|
| `hero` | `HERO` | Top Section | `false` |
| `about` | `ABOUT` | About | `false` |
| `gallery` | `GALLERY` | Product/Services/Features | `true` |
| `footer` | `FOOTER` | Footer | `false` |

### Extra Sections (added on-demand by user)
| Key | Type | Label | Icon |
|---|---|---|---|
| `video` | `VIDEO` | Video | PlayCircleOutlined |
| `vision` | `VISION` | Goals, Vision & Mission | AimOutlined |
| `blog` | `BLOG` | Blog Posts | ReadOutlined |
| `team` | `TEAM` | Team | TeamOutlined |
| `faq` | `FAQ` | FAQ | QuestionCircleOutlined |
| `testimonials` | `TESTIMONIALS` | Testimonials | StarOutlined |
| `custom` | `CUSTOM` | Custom Section | FileTextOutlined |
| `ranking` | `RANKING` | Top Authors | TrophyOutlined |

---

## 3. Shared Section Object Shape

Every section object has this base shape:

```json
{
  "type": "HERO",
  "style": 1,
  "is_hidden": false,
  "colors": { ... }
}
```

All other fields are section-specific (see Section 4).

---

## 4. Section Schemas & Style Variants

### 4.1 HERO (`HeroSection.js`)

**Props**: `title`, `subtitle`, `description`, `image_url`, `style`, `colors`, `is_hidden`

**Default colors**:
```js
title:    '#0f3460'
accent:   '#c0392b'
subtitle: '#0f172a'
body:     '#475569'
bg:       '#F9FBFF'
```

**Title rendering**: First word uses `colors.title`, remaining words use `colors.accent`.

| Style | CSS Class | Layout Description |
|---|---|---|
| **1** | `lpv2-hero-s1` | Two-column: text left, image right. Image has `borderRadius: 16px`. |
| **2** | `lpv2-hero-s2` | Full-bleed cinematic. `background-image` fills section. Gradient overlay (`lpv2-hero-s2-overlay`). All text centered, white by default. |
| **3** | `lpv2-hero-s3` | Full-bleed image + centered text, no heavy overlay. |
| **4** | `lpv2-hero-s4` | Full-bleed image + text pinned to the LEFT side over a light overlay. |
| **5** | `lpv2-hero-s5` | Magazine split: image fills LEFT half, text on RIGHT. |
| **6** | `lpv2-hero-s6` | Minimal dark. Default bg is `#0f172a`. Huge centered title, image below text. Body text at `rgba(255,255,255,0.55)`. |
| **0/default** | `lpv2-hero-section` | Full-width bg image with overlay, centered content. |

**JSON Example**:
```json
{
  "type": "HERO",
  "title": "Welcome to Our Shop",
  "subtitle": "Quality products, fast delivery",
  "description": "Discover our handmade goods from Cambodia.",
  "image_url": "",
  "style": 2,
  "is_hidden": false,
  "colors": { "title": "#ffffff", "accent": "#f59e0b", "subtitle": "#f0f0f0", "body": "rgba(255,255,255,0.8)", "bg": "#0f172a" }
}
```

---

### 4.2 ABOUT (`AboutSection.js`)

**Props**: `title`, `description`, `image_url`, `style`, `colors`, `is_hidden`

**Default colors**:
```js
title:  '#0f3460'
accent: '#2b45a8'
body:   '#444444'
bg:     '#ffffff'
```

| Style | CSS Class | Layout Description |
|---|---|---|
| **1** | `lpv2-about-section / lpv2-about-inner` | Image left (rectangular), text right. |
| **2** | `lpv2-about-s2` | Circular image LEFT, underline + title RIGHT. |
| **3** | `lpv2-about-s3` | Text LEFT (with color underline), circular image RIGHT. |
| **4** | `lpv2-about-s4` | Text LEFT (with underline), rectangular image RIGHT. |
| **5** | `lpv2-about-s5` | Text only, left-aligned, with accent underline. No image. |
| **6** | `lpv2-about-s6` | Text only, centered, with accent underline. No image. |
| **7** | `lpv2-about-s7` | Split panel: colored left half (`accent` bg) + image, white right half with text. |
| **8** | `lpv2-about-s8` | Colored strip left (`accent` bg, no image), white right with text. |

> Styles 2–4 and 7 use a `.lpv2-about-sN-underline` bar styled with `background: accent`.

**JSON Example**:
```json
{
  "type": "ABOUT",
  "title": "About Our Store",
  "description": "We are a family-run shop in Phnom Penh.",
  "image_url": "",
  "style": 3,
  "is_hidden": false,
  "colors": { "title": "#0f3460", "accent": "#2b45a8", "body": "#444444", "bg": "#ffffff" }
}
```

---

### 4.3 GALLERY (`GallerySection.js`)

**Props**: `title`, `description`, `images[]`, `style`, `colors`, `is_hidden`

Each item in `images[]`:
```json
{ "image_url": "", "name": "Product Name", "description": "Short desc" }
```

**Default colors**:
```js
title:  '#0f3460'
accent: '#2b45a8'
body:   '#475569'
bg:     '#f8fafd'
```

| Style | CSS Class | Layout Description |
|---|---|---|
| **1** | `lpv2-gallery-section` | Classic uniform image grid. |
| **2** | `lpv2-gallery-s2` | Product cards — image top, name + description below. |
| **3** | `lpv2-gallery-s3` | List view — image LEFT (square), name + description RIGHT with accent underline. |
| **4** | `lpv2-gallery-s4` | Featured grid — 1 large image left, 2×2 small grid right. |
| **5** | `lpv2-gallery-s5` | Featured grid reversed — 2×2 grid left, 1 large image right. |
| **6** | `lpv2-gallery-s6` | CSS masonry columns, natural varying heights. |
| **7** | `lpv2-gallery-s7` | Spotlight — 1 full-width top image, row of 3 thumbnails below. |
| **8** | `lpv2-gallery-s8` | Strip — horizontal scroll strip of images. |
| **9** | `lpv2-gallery-s9` | Polaroid — white-bordered cards with name caption below. |
| **10** | `lpv2-gallery-s10` | Cinematic — 16:9 widescreen stacked; name overlay on hover. |
| **11** | `lpv2-gallery-s11` | Triptych — 3 equal tall columns (uses first 3 items). |
| **12** | `lpv2-gallery-s12` | Bento — asymmetric bento grid (uses first 5 items), `lpv2-gallery-s12-cell--0` to `--4`. |
| **13** | `lpv2-gallery-s13` | Magazine — 1 large main LEFT, 2 stacked RIGHT. |
| **14** | `lpv2-gallery-s14` | Overlap — staggered overlapping card stack (uses first 5 items). |
| **15** | `lpv2-gallery-s15` | Zigzag — alternating image left/right with text; even rows get `.reverse`. |
| **16** | `lpv2-gallery-s16` | Wall — tight no-gap grid. |

**JSON Example**:
```json
{
  "type": "GALLERY",
  "title": "Our Products",
  "description": "Browse our bestsellers",
  "images": [
    { "image_url": "https://...", "name": "Traditional Scarf", "description": "Handwoven" },
    { "image_url": "https://...", "name": "Ceramic Bowl", "description": "Artisan crafted" }
  ],
  "style": 2,
  "is_hidden": false,
  "colors": { "title": "#0f3460", "accent": "#2b45a8", "body": "#475569", "bg": "#f8fafd" }
}
```

---

### 4.4 FOOTER (`FooterSection.js`)

**Props**: `title`, `description`, `phone`, `email`, `location`, `logo_url`, `social_links[]`, `style`, `colors`, `is_hidden`

**`social_links[]` item shape**:
```json
{ "type": "facebook|instagram|telegram|twitter", "handle": "https://...", "url": "https://..." }
```

**Default bg** depends on style:
- Style 1 (dark nav): `#1e293b`
- Style 2 (light): `#f8fafd`
- Style 3 (dark 3-col): `#1e293b`

| Style | CSS Class | Layout Description |
|---|---|---|
| **1** | `lpv2-footer-s1` | Dark navy footer — logo + contact left, social icons + copyright bottom strip. |
| **2** | `lpv2-footer-s2` | Light minimal centered — logo, title, contact, social links, copyright. |
| **3** | `lpv2-footer-s3` | Dark 3-column grid — logo/tagline col, contact col, follow-us col. |

**Text colors (auto-computed)**:
- Style 1 & 3 (dark): text `rgba(255,255,255,0.85)`, subtext `rgba(255,255,255,0.55)`
- Style 2 (light): text `#0f3460`, subtext `#475569`

**JSON Example**:
```json
{
  "type": "FOOTER",
  "title": "Contact Us",
  "description": "© 2025 My Shop. All rights reserved.",
  "email": "hello@myshop.com",
  "phone": "+855 088-888-9999",
  "location": "Phnom Penh, Cambodia",
  "logo_url": "",
  "social_links": [
    { "type": "facebook", "handle": "https://facebook.com/myshop" },
    { "type": "telegram", "handle": "https://t.me/myshop" }
  ],
  "style": 1,
  "is_hidden": false
}
```

---

### 4.5 VIDEO (`VideoSection.js`)

**Props**: `title`, `description`, `videos[]`, `style`, `colors`, `is_hidden`

**Default colors**: Same as Gallery (`title: #0f3460`, `accent: #2b45a8`, `body: #475569`, `bg: #f8fafd`)

Each video item:
```json
{ "url": "https://youtube.com/...", "title": "Video Title", "thumbnail": "" }
```

**JSON Example**:
```json
{
  "type": "VIDEO",
  "title": "Watch Our Story",
  "description": "See how we make our products.",
  "videos": [ { "url": "https://youtube.com/watch?v=xxx", "title": "Our Process" } ],
  "style": 1,
  "is_hidden": false,
  "colors": { "title": "#0f3460", "accent": "#2b45a8", "body": "#475569", "bg": "#f8fafd" }
}
```

---

### 4.6 VISION (`VisionSection.js`)

**Props**: `title`, `description`, `goals_title`, `goals_description`, `vision_title`, `vision_description`, `mission_title`, `mission_description`, `style`, `colors`, `is_hidden`

**Default colors**:
```js
title:         '#0f3460'
body:          '#444444'
bg:            '#ffffff'
accent:        '#2b45a8'
goal_color:    '#7b1d1d'   // dark red
vision_color:  '#4a5a10'   // dark green
mission_color: '#1a2b6e'   // dark blue
```

Internally the 3 sub-items (goal, vision, mission) are mapped to icons: `TrophyOutlined`, `EyeOutlined`, `AimOutlined` with numbered labels `01`, `02`, `03`.

| Style | CSS Class | Layout Description |
|---|---|---|
| **1** | `lpv2-vision-section` | 3 cards with accent background icon circles, split layout. |
| **2** | `lpv2-vision-s2` | 3-column colored cards. Each card background = its `color` (goal/vision/mission). |
| **3** | `lpv2-vision-s3` | Horizontal icon rows — colored icon circle, title + description text, number on right. |
| **4** | `lpv2-vision-s4` | Numbered steps — number, divider, icon, title, description. Dark style. |
| **5** | `lpv2-vision-s5` | Feature grid — icon circle, title, description, centered. |
| **6** | `lpv2-vision-s6` | Split panel — accent-bg column left (title + desc), list of icon rows right. |

**JSON Example**:
```json
{
  "type": "VISION",
  "title": "Our Purpose",
  "description": "We exist to empower communities.",
  "goals_title": "Our Goal",
  "goals_description": "Connect 1 million users by 2026.",
  "vision_title": "Our Vision",
  "vision_description": "A digitally connected Cambodia.",
  "mission_title": "Our Mission",
  "mission_description": "Build tools that empower creators.",
  "style": 2,
  "is_hidden": false,
  "colors": {
    "title": "#0f3460", "body": "#444", "bg": "#ffffff", "accent": "#2b45a8",
    "goal_color": "#7b1d1d", "vision_color": "#4a5a10", "mission_color": "#1a2b6e"
  }
}
```

---

### 4.7 BLOG (`BlogSection.js`)

Blog posts fetched automatically from the community. No manual content needed.

**Props**: `title`, `description`, `style`, `colors`, `is_hidden`

**JSON Example**:
```json
{
  "type": "BLOG",
  "title": "Latest from Our Blog",
  "description": "Explore the latest posts from our community.",
  "style": 1,
  "is_hidden": false,
  "colors": { "title": "#0f3460", "accent": "#2b45a8", "body": "#475569", "bg": "#f8fafd" }
}
```

---

### 4.8 TEAM (`TeamSection.js`)

**Props**: `title`, `description`, `members[]`, `style`, `colors`, `is_hidden`

Each member:
```json
{ "name": "Jane Smith", "role": "CEO", "image_url": "" }
```

**JSON Example**:
```json
{
  "type": "TEAM",
  "title": "Meet Our Team",
  "description": "The people behind our mission.",
  "members": [
    { "name": "Sokha Chan", "role": "Founder & CEO", "image_url": "" },
    { "name": "Dara Lim", "role": "Head of Design", "image_url": "" }
  ],
  "style": 1,
  "is_hidden": false,
  "colors": { "title": "#0f3460", "accent": "#2b45a8", "bg": "#f8fafd" }
}
```

---

### 4.9 FAQ (`FAQSection.js`)

**Props**: `title`, `faq_items[]`, `style`, `colors`, `is_hidden`

Each FAQ item:
```json
{ "q": "What is...?", "a": "It is..." }
```

**JSON Example**:
```json
{
  "type": "FAQ",
  "title": "Frequently Asked Questions",
  "faq_items": [
    { "q": "Do you ship internationally?", "a": "Yes, we ship to 20+ countries." },
    { "q": "What payment methods are accepted?", "a": "KHQR, credit card, and Serey Coin." }
  ],
  "style": 1,
  "is_hidden": false,
  "colors": { "title": "#0f3460", "accent": "#2b45a8", "bg": "#ffffff" }
}
```

---

### 4.10 TESTIMONIALS (`TestimonialsSection.js`)

**Props**: `title`, `testimonial_items[]`, `style`, `colors`, `is_hidden`

Max 6 items. Each item:
```json
{ "name": "John Doe", "role": "Customer", "quote": "Great experience! (max 300 chars)", "image_url": "" }
```

**JSON Example**:
```json
{
  "type": "TESTIMONIALS",
  "title": "What Our Customers Say",
  "testimonial_items": [
    { "name": "Riya Patel", "role": "Regular Customer", "quote": "Best shop in town!", "image_url": "" }
  ],
  "style": 1,
  "is_hidden": false,
  "colors": { "title": "#0f3460", "body": "#444444", "accent": "#2b45a8", "bg": "#ffffff" }
}
```

---

### 4.11 CUSTOM (`CustomSection.js`)

**Props**: `title`, `description`, `button_label`, `button_url`, `image_url`, `image_url_2`, `style`, `colors`, `is_hidden`

**Default colors**:
```js
title:  '#0f3460'
body:   '#444444'
bg:     '#ffffff'
accent: '#2b45a8'
```

The button renders as `<a>` with `background: accent`.

| Style | CSS Class | Layout Description |
|---|---|---|
| **1** | `lpv2-custom-section` | Split Right — text left with accent underline, image right. |
| **2** | `lpv2-custom-s2` | Split Left — image left, text right with accent underline. |
| **3** | `lpv2-custom-s3` | Centered — image above, title centered, underline centered, description centered. |
| **4** | `lpv2-custom-s4` | Banner — full-width image as background (`lpv2-custom-s4-bg`), dark overlay, white text centered. |
| **5** | `lpv2-custom-s5` | Card — image on top of a styled card, accent underline before title, body below. |
| **6** | `lpv2-custom-s6` | Highlight split — accent-colored LEFT panel (title + desc + btn), white RIGHT panel (1 or 2 images). Supports `image_url_2`. |

**JSON Example**:
```json
{
  "type": "CUSTOM",
  "title": "Our Commitment",
  "description": "Every product we sell supports local artisans.",
  "button_label": "Learn More",
  "button_url": "https://serey.io",
  "image_url": "",
  "image_url_2": "",
  "style": 6,
  "is_hidden": false,
  "colors": { "title": "#ffffff", "body": "#f0f0f0", "bg": "#f8f9ff", "accent": "#2b45a8" }
}
```

---

### 4.12 RANKING (`RankingSection.js`)

Top authors auto-fetched from community posts. No manual content.

**Props**: `title`, `description`, `style`, `colors`, `is_hidden`

**JSON Example**:
```json
{
  "type": "RANKING",
  "title": "Top Authors",
  "description": "Most active bloggers this month.",
  "style": 1,
  "is_hidden": false,
  "colors": { "title": "#0f3460", "accent": "#2b45a8", "body": "#475569", "bg": "#f8fafd" }
}
```

---

## 5. Color System

### 5.1 Controlled Color Slots per Section

Each section's `colors` object accepts these keys. Values are applied as inline styles by the renderer.

| Section | `title` | `accent` | `body` | `bg` | Extra |
|---|---|---|---|---|---|
| hero | ✓ | ✓ | ✓ | ✓ | `subtitle` |
| about | ✓ | ✓ | ✓ | ✓ | — |
| gallery | ✓ | ✓ | ✓ | ✓ | — |
| footer | — | ✓ | — | ✓ | Auto text/sub colors based on dark/light |
| video | ✓ | ✓ | ✓ | ✓ | — |
| vision | ✓ | ✓ | ✓ | ✓ | `goal_color`, `vision_color`, `mission_color` |
| blog | ✓ | ✓ | ✓ | ✓ | — |
| team | ✓ | ✓ | — | ✓ | — |
| faq | ✓ | ✓ | — | ✓ | — |
| testimonials | ✓ | ✓ | ✓ | ✓ | — |
| custom | ✓ | ✓ | ✓ | ✓ | — |
| ranking | ✓ | ✓ | ✓ | ✓ | — |

### 5.2 Default Color Values (sourced from component code)

| Color Key | Default Value | Usage |
|---|---|---|
| `title` | `#0f3460` | Section headings |
| `accent` | `#2b45a8` (most) / `#c0392b` (hero) | Underlines, badges, icon backgrounds, buttons |
| `body` | `#444444` or `#475569` | Paragraph text |
| `bg` | `#ffffff` or `#f8fafd` | Section background |
| `subtitle` (hero only) | `#0f172a` | Hero subtitle |
| `goal_color` | `#7b1d1d` | Dark red card (Vision) |
| `vision_color` | `#4a5a10` | Dark green card (Vision) |
| `mission_color` | `#1a2b6e` | Dark blue card (Vision) |
| Footer dark bg | `#1e293b` | Styles 1 & 3 |
| Footer light bg | `#f8fafd` | Style 2 |

### 5.3 Suggested Palettes by Site Mood

| Mood | `title` | `accent` | `body` | `bg` |
|---|---|---|---|---|
| Corporate / Professional | `#0f3460` | `#2b45a8` | `#444444` | `#ffffff` |
| E-commerce / Warm | `#b45309` | `#047857` | `#555555` | `#fffbeb` |
| Tech / Startup | `#0f172a` | `#6C63FF` | `#475569` | `#f8fbff` |
| Bold / Energy | `#c0392b` | `#f59e0b` | `#333` | `#fff` |
| Minimal / Dark | `#ffffff` | `#f59e0b` | `rgba(255,255,255,0.7)` | `#0f172a` |
| NGO / Community | `#064e3b` | `#10b981` | `#374151` | `#f0fdf4` |
| Education | `#003399` | `#2E6BFF` | `#444` | `#f8fbff` |
| Food / Restaurant | `#7c2d12` | `#ef4444` | `#555` | `#fff7ed` |

---

## 6. Style Variant Reference

### Quick-Select by Personality

| Personality | Hero | About | Gallery | Custom |
|---|---|---|---|---|
| Clean / Minimal | 1 | 1 | 2 | 3 |
| Cinematic / Bold | 2 | 7 | 4 | 4 |
| Magazine / Editorial | 5 | 4 | 13 | 6 |
| Dark / Dramatic | 6 | 8 | 10 | 4 |
| Playful / Creative | 3 | 2 | 9 | 5 |
| Organized / Corporate | 4 | 3 | 3 | 2 |
| Photography Portfolio | 2 | 5 | 6 | 2 |
| Product Showcase | 1 | 4 | 15 | 1 |

---

## 7. Required vs Optional Fields

| Section | **Required** | **Optional** |
|---|---|---|
| HERO | `title` | `subtitle`, `description`, `image_url` |
| ABOUT | `title`, `description` | `image_url` |
| GALLERY | `title`, at least 1 item in `images[]` | `description` |
| FOOTER | `title` | `email`, `phone`, `location`, `logo_url`, `social_links[]`, `description` |
| VIDEO | `title`, `videos[]` | `description` |
| VISION | `title` | `description`, all `*_title` / `*_description` fields |
| BLOG | `title` | `description` |
| TEAM | `title`, `members[].name` | `description`, `members[].role`, `members[].image_url` |
| FAQ | `title`, `faq_items[].q + .a` | — |
| TESTIMONIALS | `title`, `testimonial_items[].quote` (max 300 chars) | `.name`, `.role`, `.image_url` (max 6 items) |
| CUSTOM | `title`, `description` | `button_label`, `button_url`, `image_url`, `image_url_2` |
| RANKING | `title` | `description` |

---

## 8. AI Section Recommendation by Site Type

| Site Type | Sections (ordered) | Notes |
|---|---|---|
| Online Shop | hero, about, gallery, testimonials, faq, footer | gallery = products, FAQ for returns/shipping |
| Restaurant / Food | hero, gallery, about, testimonials, footer | gallery = menu items |
| Community / Blog | hero, about, blog, ranking, footer | blog + ranking auto-fetch |
| NGO / Charity | hero, about, vision, team, testimonials, footer | vision for goal/mission |
| Educational | hero, about, blog, team, faq, footer | team = teachers/staff |
| Fitness / Sports | hero, about, video, gallery, testimonials, footer | video for workouts |
| Tech / SaaS | hero, about, gallery, vision, faq, testimonials, footer | gallery = features |
| Photography Portfolio | hero, gallery, about, footer | gallery with style 6 or 13 |
| Professional Service | hero, about, team, faq, custom, footer | custom for case study |
| News / Media | hero, blog, ranking, video, footer | data-driven sections |

---

## 9. API Contract

### GET Landing Page
```
GET  /api/v2/landing-pages?community_id={communityId}
Authorization: Bearer {token}

Response 200:
{
  "status": true,
  "landing_page": {
    "id": 123,
    "community_id": 456,
    "content": [ /* array of section objects */ ]
  }
}
```

### CREATE / UPDATE Landing Page
```
POST /api/v2/landing-pages
Authorization: Bearer {token}
Content-Type: application/json

Body:
{
  "community_id": 456,
  "content": [ /* array of section objects */ ]
}

Response 200:
{ "status": true, "landing_page": { ... } }
```

> **AI Integration**: Your backend receives a natural-language prompt (e.g. *"I run a handmade jewellery shop in Phnom Penh"*) and returns a valid `content` array. The frontend POSTs this directly to the save API. No other transformation is needed.

---

## 10. Full Example — Online Shop Landing Page

```json
[
  {
    "type": "HERO",
    "title": "Welcome to Our Shop",
    "subtitle": "Handmade goods from Cambodia",
    "description": "Premium artisan products delivered to your door.",
    "image_url": "",
    "style": 1,
    "is_hidden": false,
    "colors": { "title": "#b45309", "accent": "#047857", "subtitle": "#1a1a2e", "body": "#555555", "bg": "#fffbeb" }
  },
  {
    "type": "ABOUT",
    "title": "About Our Store",
    "description": "We are a family-run business passionate about traditional Cambodian crafts.",
    "image_url": "",
    "style": 4,
    "is_hidden": false,
    "colors": { "title": "#b45309", "accent": "#047857", "body": "#444444", "bg": "#ffffff" }
  },
  {
    "type": "GALLERY",
    "title": "Our Products",
    "description": "Browse our bestsellers",
    "images": [
      { "name": "Traditional Scarf", "description": "Handwoven in Phnom Penh", "image_url": "" },
      { "name": "Ceramic Bowl Set", "description": "Artisan crafted", "image_url": "" },
      { "name": "Silk Bag", "description": "100% natural silk", "image_url": "" }
    ],
    "style": 2,
    "is_hidden": false,
    "colors": { "title": "#b45309", "accent": "#047857", "body": "#475569", "bg": "#f0fdf4" }
  },
  {
    "type": "TESTIMONIALS",
    "title": "What Our Customers Say",
    "testimonial_items": [
      { "name": "Sarah K.", "role": "Returning Customer", "quote": "Absolutely love the quality. Will order again!", "image_url": "" }
    ],
    "style": 1,
    "is_hidden": false,
    "colors": { "title": "#b45309", "accent": "#047857", "body": "#444444", "bg": "#ffffff" }
  },
  {
    "type": "FAQ",
    "title": "Frequently Asked Questions",
    "faq_items": [
      { "q": "Do you ship internationally?", "a": "Yes, we ship to over 20 countries." },
      { "q": "What payment methods do you accept?", "a": "KHQR, credit card, and Serey Coin." }
    ],
    "style": 1,
    "is_hidden": false,
    "colors": { "title": "#b45309", "accent": "#047857", "bg": "#fffbeb" }
  },
  {
    "type": "FOOTER",
    "title": "Contact Us",
    "description": "© 2025 My Shop. All rights reserved.",
    "email": "hello@myshop.com",
    "phone": "+855 088-888-9999",
    "location": "Phnom Penh, Cambodia",
    "logo_url": "",
    "social_links": [
      { "type": "facebook", "handle": "https://facebook.com/myshop" },
      { "type": "telegram", "handle": "https://t.me/myshop" }
    ],
    "style": 1,
    "is_hidden": false
  }
]
```

---

## 11. Frontend ↔ Backend Compatibility

### 11.1 Gap Analysis (current state)

The **frontend** (Serey V2 Landing Page builder / renderer) stores sections as JSON objects with **string `type` keys** (e.g. `"HERO"`, `"ABOUT"`) and rich, section-specific fields.

The **backend** (`builder_chat.py` / `schemas/blueprint.py`) was written around an older model that uses **numeric `type` keys** (e.g. `1`, `2`, `3`, `4`) with a flat, generic `ContentBlock`.

| Dimension | Frontend (V2 JSON) | Backend (current schema) |
|---|---|---|
| Section identifier | String `"type": "HERO"` | Integer `"type": 1` |
| Sections supported | 12 (`HERO … RANKING`) | 4 (`1`=Hero, `2`=About, `3`=Gallery, `4`=Footer) |
| `images[]` items | `{ image_url, name, description }` | `list[str]` (plain URL strings) |
| `social_links[]` items | `{ type, handle, url? }` | `dict[str, str]` (same — OK) |
| GALLERY extra fields | `name`, `description` per image | ❌ missing |
| FOOTER extra fields | `phone`, `email`, `location`, `logo_url`, `social_links` | ✓ present |
| Section-specific fields | VISION sub-fields, VIDEO `videos[]`, FAQ `faq_items[]`, TEAM `members[]`, etc. | ❌ not modelled |
| `colors` object | Per-section color map `{ title, accent, body, bg, … }` | ❌ not modelled |
| `is_hidden` flag | ✓ present | ✓ present |
| Blueprint wrapper | Raw `content[]` array POSTed to `/api/v2/landing-pages` | `PageBlueprint { community_id, template, content[] }` |
| Save endpoint | `POST /api/v2/landing-pages` (Serey main API) | AI backend returns blueprint; frontend must POST to Serey API |
| AI system prompt | — | Uses old numeric type/style guide — must be replaced with this document |

### 11.2 Required Backend Changes

#### a. Rewrite `ContentBlock` to match V2 section schema

Replace the numeric-type generic block with a typed, section-specific schema:

```python
# schemas/blueprint.py  (new)

from typing import Literal, Union, Any
from pydantic import BaseModel, Field

class SectionBase(BaseModel):
    type: str          # e.g. "HERO", "ABOUT", …
    style: int = 1
    is_hidden: bool = False
    colors: dict[str, str] | None = None

class ImageItem(BaseModel):
    image_url: str = ""
    name: str | None = None
    description: str | None = None

class VideoItem(BaseModel):
    url: str
    title: str | None = None
    thumbnail: str | None = None

class MemberItem(BaseModel):
    name: str
    role: str | None = None
    image_url: str = ""

class FAQItem(BaseModel):
    q: str
    a: str

class TestimonialItem(BaseModel):
    name: str | None = None
    role: str | None = None
    quote: str
    image_url: str = ""

class SocialLink(BaseModel):
    type: str          # "facebook" | "instagram" | "telegram" | "twitter"
    handle: str
    url: str | None = None

class ContentBlock(SectionBase):
    # HERO / ABOUT / CUSTOM / etc.
    title: str | None = None
    subtitle: str | None = None
    description: str | None = None
    image_url: str | None = None
    image_url_2: str | None = None
    button_label: str | None = None
    button_url: str | None = None
    # FOOTER
    phone: str | None = None
    email: str | None = None
    location: str | None = None
    logo_url: str | None = None
    social_links: list[SocialLink] | None = None
    # GALLERY
    images: list[ImageItem] | None = None
    # VIDEO
    videos: list[VideoItem] | None = None
    # VISION
    goals_title: str | None = None
    goals_description: str | None = None
    vision_title: str | None = None
    vision_description: str | None = None
    mission_title: str | None = None
    mission_description: str | None = None
    # TEAM
    members: list[MemberItem] | None = None
    # FAQ
    faq_items: list[FAQItem] | None = None
    # TESTIMONIALS
    testimonial_items: list[TestimonialItem] | None = None
```

`PageBlueprint` stays the same but now holds a `list[ContentBlock]` with string types.

#### b. Update `BUILDER_SYSTEM_PROMPT` in `builder_chat.py`

Replace the old numeric-type prompt with the V2 string-type guide from this document:

- Use **string type keys** exactly: `"HERO"`, `"ABOUT"`, `"GALLERY"`, `"FOOTER"`, `"VIDEO"`, `"VISION"`, `"BLOG"`, `"TEAM"`, `"FAQ"`, `"TESTIMONIALS"`, `"CUSTOM"`, `"RANKING"`.
- Reference Section 4 of this document for all field names and valid style numbers.
- Reference Section 8 for section-order recommendations.
- Reference Section 5 for color palette suggestions.
- The AI must output a `blueprint.content[]` that can be POSTed **directly** to `POST /api/v2/landing-pages` as the `content` field.

Minimal skeleton for the new system prompt:

```
You are an expert AI page builder for Serey V2 landing pages.

SECTION TYPES (use these exact string keys):
HERO, ABOUT, GALLERY, FOOTER, VIDEO, VISION, BLOG, TEAM, FAQ, TESTIMONIALS, CUSTOM, RANKING

For each section output: { "type": "HERO", "style": <int>, "is_hidden": false, "colors": {...}, ...section-specific fields }

Style numbers and section-specific fields are defined in the AI training reference.
Always include HERO first and FOOTER last.
Return ONLY the JSON envelope: { "reply": "...", "blueprint": { "community_id": <int>, "content": [...] } | null, "patches": [...] | null }
```

#### c. Update `PatchCommand` to use string `type`

```python
class PatchCommand(BaseModel):
    action: str   # "update_block" | "add_block" | "delete_block"
    type: str     # e.g. "HERO" — matches section type string
    updates: dict[str, Any]
```

### 11.3 Required Frontend Changes

The frontend already uses the V2 string-type JSON natively via `LandingBuilderV2.js`. **No structural changes are needed** to the builder or renderer.

The frontend integration layer (the page that calls this AI backend) must:

1. **POST to AI backend** `POST /api/builder/chat` with `{ message, user_id, session_id, community_id }`.
2. **Receive** `BuilderChatResponse` → extract `blueprint.content[]` (or apply `patches` to existing state).
3. **Apply patches** client-side: iterate `patches[]`, match by `type` string, merge `updates` into the matching section object.
4. **Save to Serey** by calling `POST /api/v2/landing-pages` with `{ community_id, content: <blueprint.content> }` — the array is ready as-is.
5. **Normal chat** (`/api/chat`) is unchanged — `chat.py` / `ChatResponse` needs no modifications.

### 11.4 Endpoint Summary (final state)

| Purpose | Method + Path | Auth | Notes |
|---|---|---|---|
| AI builder chat | `POST /api/builder/chat` | `X-Serey-API-Key` | Returns `{ reply, blueprint, patches }` |
| AI info chat (Soriya) | `POST /api/chat` | `X-Serey-API-Key` | Returns `{ reply, links }` — **unchanged** |
| Get landing page | `GET /api/v2/landing-pages?community_id={}` | Bearer token | Serey main API |
| Save landing page | `POST /api/v2/landing-pages` | Bearer token | Body: `{ community_id, content: [...] }` |

> **Key rule**: The AI backend never calls the Serey save API directly. It only returns a blueprint. The frontend is responsible for the save call.
