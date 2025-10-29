# SIGE Fleet Dashboard - Design Guidelines

## Design Approach
**System**: Bootstrap 5 Material-influenced dashboard design, drawing patterns from Linear's clarity, Notion's data density, and modern SaaS dashboards (Stripe, HubSpot). Focus on information hierarchy and data visualization excellence for enterprise fleet management.

## Typography System

**Font Stack**: 
- Primary: Inter via Google Fonts CDN (weights: 400, 500, 600, 700)
- Monospace: 'Roboto Mono' for numerical data

**Hierarchy**:
- Page Title: 2rem (32px), weight 700, tracking tight
- Section Headers: 1.5rem (24px), weight 600
- Card Titles: 1.125rem (18px), weight 600
- KPI Labels: 0.75rem (12px), weight 500, uppercase, tracking wide
- KPI Values: 1.75rem (28px), weight 700, tabular-nums
- Body Text: 1rem (16px), weight 400
- Helper Text: 0.875rem (14px), weight 400

## Layout System

**Spacing Primitives**: Tailwind units of 2, 3, 4, 6, 8 (p-2, mb-4, gap-6, py-8)
- Card padding: p-4 (mobile), p-6 (desktop)
- Section spacing: mb-6 between major sections
- Grid gaps: gap-4 (mobile), gap-6 (desktop)

**Dashboard Structure**:
- Main content area: max-width container with px-3 (mobile), px-4 (desktop)
- Grid system: 12-column responsive grid
- KPI Cards Row: 4 columns desktop (col-lg-3), 2 columns tablet (col-md-6), stack mobile

## Component Library

**KPI Cards** (4 cards in top row):
- Each card: rounded corners (8px), subtle shadow (Bootstrap shadow-sm)
- Icon area: 48x48px circle with gradient background, positioned top-left
- Value: Large bold numerals, right-aligned
- Label: Uppercase small text below icon
- Trend indicator: Small badge with arrow icon (↑/↓) and percentage
- Optional: Mini sparkline chart (20px height) at card bottom

**Filter Bar** (below KPI cards):
- Horizontal layout with inline form controls
- Elements: Date range picker, vehicle type dropdown, status dropdown, search input, export button
- Responsive: Stack vertically on mobile with mb-3 spacing
- Height: 56px on desktop for visual consistency

**Chart Sections** (2 columns on desktop):
- Left Column (col-lg-8): Primary TCO trend line chart, height 400px
- Right Column (col-lg-4): Two stacked cards - pie chart (200px) and bar chart (200px)
- Chart container: White card with p-4, mb-4
- Chart header: Flex layout with title left, action dropdown right

**Data Table Section**:
- Full-width responsive table with Bootstrap classes
- Sticky header on scroll
- Row hover states
- Column headers: Sort indicators, align with data
- Action column: Compact icon buttons (view, edit, delete)
- Pagination: Bootstrap pagination component, centered below table

**Empty States**:
- Centered content with illustration placeholder (200x200px)
- Message text and CTA button below

## Icons & Assets

**Icon Library**: Bootstrap Icons via CDN
- Dashboard: speedometer2, truck, fuel-pump, tools, cash-stack
- Actions: filter, download, search, three-dots-vertical
- Trends: arrow-up-circle, arrow-down-circle

**Chart.js Configuration**:
- Line charts: Curved lines (tension: 0.4), gradient fills
- Grid: Subtle, dashed lines
- Tooltips: Custom styled with shadow
- Legend: Positioned top-right, horizontal layout

**Images**: No hero images required - this is a data dashboard interface

## Interaction Patterns

**Loading States**: 
- Skeleton screens for KPI cards and charts
- Pulse animation on data refresh

**Responsive Behavior**:
- Sidebar: Collapsible on mobile with hamburger toggle
- KPI cards: 4→2→1 column progression
- Charts: Full width stack on mobile
- Table: Horizontal scroll on mobile with sticky first column

**Micro-interactions**:
- Card hover: Subtle lift (transform translateY(-2px))
- Button states: Standard Bootstrap active/hover
- Filter changes: 300ms data transition

## Accessibility

- ARIA labels for all interactive elements
- Keyboard navigation for filters and tables
- Focus indicators on all focusable elements
- Chart data accessible via tables (sr-only)
- Minimum touch target: 44x44px

## Dashboard-Specific Guidelines

**Information Density**: High - maximize data visibility while maintaining clarity
**Update Frequency**: Real-time indicator badge for live data sections
**Export Functions**: Clear download options for reports (PDF, Excel, CSV)
**Drill-down Pattern**: KPI cards clickable to filtered table view
**Multi-tenant UX**: Tenant selector in navbar, persistent across sessions