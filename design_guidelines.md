# EnterpriseSync/SIGE Landing Page - Design Guidelines

## Design Approach
**Reference-Based**: Drawing from modern B2B SaaS leaders (Linear, Stripe, HubSpot, Notion marketing pages) combined with Bootstrap 5. Focus on trust-building, information clarity, and premium positioning for construction industry decision-makers. Brazilian Portuguese throughout.

## Typography System
**Font Stack**: Inter via Google Fonts (weights: 400, 500, 600, 700)

**Hierarchy**:
- Hero Headline: 3.5rem (56px) desktop / 2.5rem (40px) mobile, weight 700, line-height 1.1
- Section Headers: 2.5rem (40px) desktop / 2rem (32px) mobile, weight 700
- Subsection Titles: 1.5rem (24px), weight 600
- Feature Card Titles: 1.25rem (20px), weight 600
- Pricing Plan Names: 1.75rem (28px), weight 700
- Body Text: 1.125rem (18px), weight 400, line-height 1.7
- Helper/Caption: 0.875rem (14px), weight 500

## Layout System
**Spacing Primitives**: Tailwind units of 4, 6, 8, 12, 16, 20
- Section padding: py-20 desktop, py-12 mobile
- Container: max-w-7xl with px-4
- Grid gaps: gap-6 (cards), gap-8 (sections)

**Page Structure**:
- Hero: Full viewport height (min-h-screen), centered content over background image
- Content sections: Alternating full-width and contained layouts
- Feature grid: 3 columns desktop (grid-cols-3), 2 tablet (md:grid-cols-2), 1 mobile
- Pricing cards: 4 columns desktop, 2 tablet, 1 mobile

## Component Library

**Hero Section**:
- Full-width background: High-quality construction site image with 40% dark overlay
- Content: Centered, max-w-4xl
- Headline + subheadline (max-w-2xl)
- CTA group: Primary button (large, px-8 py-4) + Secondary button (transparent with backdrop-blur-md background)
- Trust indicators: Small logo strip below CTAs (5-6 client logos, grayscale with opacity-70)

**Feature Module Grid** (18 modules total):
- Card design: White background, rounded-xl, p-6, hover:shadow-lg transition
- Layout per card: Icon (56x56px, green circle background) + Title + 2-line description
- 6 rows × 3 columns on desktop, responsive stack
- Each module: One Bootstrap Icon, concise title, brief benefit statement

**Pricing Section**:
- 4-card horizontal layout, equal width
- Featured plan (Professional): Elevated with shadow-xl, border-2 border-green, scale-105
- Card structure: Header (plan name + price), feature list (8-10 items with checkmarks), CTA button
- Price display: R$ prefix small, number large (2.5rem), /mês suffix small
- Annual toggle above cards: "Mensal / Anual (20% desconto)" switch

**Testimonial Section**:
- 3-column grid of testimonial cards
- Card content: Quote text (1.125rem italic) + Author photo (64x64 rounded-full) + Name + Company + Role
- Subtle quotation mark icon (large, opacity-10) as background element

**Feature Highlight Sections** (2-3 between main sections):
- Alternating image-left / image-right layouts
- Two-column: Image (55% width) + Content (45%)
- Content: Subheading + headline + description + bullet points + CTA link
- Image: Rounded-lg with subtle shadow

**Final CTA Section**:
- Full-width with gradient green background (from #198754 to darker shade)
- Centered content: Large headline + description + email input + button combo
- Social proof: "Junte-se a 500+ empresas de construção" subtext

**Footer**:
- Four-column layout: Company info + Products + Resources + Contact
- Newsletter signup integrated
- Bottom bar: Copyright + Privacy links + Social icons (LinkedIn, Instagram, YouTube)

## Icons & Visual Assets
**Icons**: Bootstrap Icons via CDN (boxes, people, graph-up, shield-check, gear, calendar, etc.)
**Images Required**:
- Hero: Modern construction site/blueprint workspace (professional, aspirational)
- Feature highlights: 2-3 dashboard screenshots or construction workers using tablets
- Testimonial photos: Professional headshots (can use placeholder services)
- Logo: EnterpriseSync/SIGE logo in header

## Interaction Patterns
**Animations**: Minimal, purposeful only
- Scroll reveal: Fade-up on sections (intersection observer)
- Card hover: Subtle lift on feature/pricing cards
- Button states: Standard Bootstrap transitions

**Responsive Behavior**:
- Hero: Reduce padding, stack CTA buttons vertically on mobile
- Feature grid: 3→2→1 column progression
- Pricing: Horizontal scroll on mobile (snap scroll) or vertical stack
- Navigation: Collapse to hamburger menu on mobile

## Accessibility
- High contrast text on all backgrounds
- Alt text for all images describing construction/business context
- ARIA labels for icon-only buttons
- Focus states on all interactive elements
- Skip navigation link

## Brazilian Portuguese Content Notes
- Formal "você" form throughout
- Industry terminology: "gestão de obras," "controle financeiro," "cronograma"
- Social proof numbers in Brazilian format (500+ empresas, R$ 2M economizados)
- Trust signals: "Suporte em português," "Dados no Brasil," "LGPD compliant"