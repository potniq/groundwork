# Groundwork Design System

Default Theme + Country Overrides

Scope: groundwork.potniq.com

⸻

1. Design Principles

Groundwork is:
	•	Calm
	•	Factual
	•	Infrastructure-like
	•	Reference-grade
	•	Neutral by default

It should feel closer to documentation or civic infrastructure than to marketing.

No gloss. No gradients. No decorative noise.

⸻

2. Color System

2.1 Default (Neutral) Theme

Primary

Token	Value	Usage
--color-navy-900	#1F2E45	Logo top layer, headings, wordmark
--color-teal-600	#2E7C82	Pin fill, links, highlights


⸻

Structural Greys

Token	Value	Usage
--color-slate-700	#4B5A6A	Transit lines, subheadings
--color-slate-500	#8A97A6	Middle layer, borders
--color-slate-300	#D3DAE2	Dividers, subtle backgrounds


⸻

Background

Token	Value	Usage
--color-bg	#F5F4F1	Page background


⸻

2.2 Usage Rules
	•	Avoid pure black (#000000)
	•	Avoid pure white (#FFFFFF) except in controlled UI components
	•	Teal should be the only saturated accent in the default theme
	•	Greys should carry most of the visual weight

⸻

3. Logo System

3.1 Logo Structure

The logo consists of:
	1.	Top map layer
	2.	Middle map layer
	3.	Bottom map layer
	4.	Transit line + nodes
	5.	Location pin
	6.	Wordmark
	7.	Subline (“by Potniq”)

⸻

3.2 Default Logo Color Mapping

Element	Color
Top layer	--color-navy-900
Middle layer	--color-slate-500
Bottom layer	--color-slate-700
Transit line	--color-slate-500
Transit nodes	Hollow, stroke --color-slate-700, no fill
Pin outer	--color-navy-900
Pin inner	--color-teal-600
Wordmark	--color-navy-900
Subline	--color-slate-700


⸻

3.3 Transit Line Styling
	•	Stroke width: 8–12% of icon height
	•	Nodes:
	•	Hollow
	•	Stroke width = 50% of line thickness
	•	Diameter = 2× line thickness
	•	Rounded caps
	•	Rounded joins

No bright filled circles. No heavy contrast nodes.

⸻

4. Typography

4.1 Logo Typography
	•	Sans-serif
	•	Clean geometric or neo-grotesk
	•	Medium weight for “Groundwork”
	•	Regular weight for “by Potniq”

Avoid:
	•	Serif
	•	Script
	•	Condensed fonts
	•	Decorative fonts

⸻

4.2 UI Typography

Hierarchy:
	•	H1: Navy 900
	•	H2: Navy 900
	•	H3: Slate 700
	•	Body: Slate 700
	•	Secondary text: Slate 500

⸻

5. Spacing System

Base unit: 4px

Recommended scale:
	•	4
	•	8
	•	12
	•	16
	•	24
	•	32
	•	48
	•	64

Logo padding:
	•	Minimum clear space = height of pin circle

⸻

6. Country-Specific Theming

Groundwork supports optional country-specific logo variants.

6.1 Design Rule

The logo structure remains identical.

Only these may change:
	•	Transit line color
	•	One map layer
	•	Pin inner fill

The wordmark remains navy.

⸻

6.2 Neutral Default Requirement

Every page must have a neutral fallback.

If country-specific tokens are not defined:
	•	Use default palette
	•	Do not break layout

⸻

6.3 Example: Norway Theme

Override:

Token	Value
--color-country-primary	#BA0C2F (Muted red)
--color-country-secondary	#00205B (Deep blue)

Application:
	•	Transit line = country primary
	•	Pin inner = country primary
	•	Bottom layer = country secondary

Greys remain unchanged.

⸻

6.4 Example: Switzerland Theme

Token	Value
--color-country-primary	#D52B1E

Use sparingly:
	•	Transit line
	•	Pin inner

⸻

6.5 Example: Spain Theme

Token	Value
--color-country-primary	#AA151B
--color-country-secondary	#F1BF00

Use:
	•	Transit line = red
	•	Bottom layer = muted yellow
	•	Pin inner = red

⸻

7. SVG Guidelines
	•	Flat fills only
	•	No gradients
	•	No drop shadows
	•	No emboss
	•	No glow effects
	•	All shapes vector
	•	Rounded corners consistent

Icon must work at:
	•	24px
	•	32px
	•	48px
	•	128px
	•	512px

Test legibility at 24px.

⸻

8. Accessibility

Minimum contrast:
	•	Text vs background: WCAG AA
	•	Avoid light grey text on off-white
	•	Transit line must not rely on color alone (shape is sufficient)

⸻

9. Non-Goals

Groundwork is not:
	•	A marketing site
	•	A lifestyle brand
	•	A tourism influencer product

Avoid:
	•	Stock photography in logo
	•	Decorative gradients
	•	Heavy flag usage
	•	Hyper-saturated color schemes

⸻

10. Future Evolution

This design system is generic.

If country-specific logos become core to the product:
	•	Country palettes may expand
	•	A theming engine may generate logo variants per slug
	•	Default neutral must always remain available

