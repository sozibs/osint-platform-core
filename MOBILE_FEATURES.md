# Mobile Features – OSINT Platform

## Overview

The OSINT Platform is designed mobile-first, adapting its layout and interactions for phones, tablets, and desktops.

---

## Responsive Layout

| Breakpoint | Device | Layout |
|---|---|---|
| < 768px | Phone | Bottom navigation + mobile header |
| 768–991px | Tablet | Slide-out drawer + top header |
| ≥ 992px | Desktop | Persistent sidebar |

---

## Navigation

### Mobile (< 768px)
- **Bottom Navigation Bar**: 5 main sections (Dashboard, Footprint, Investigate, Cyber, More)
- **Hamburger Menu**: Full-screen slide-out drawer for all modules
- **Top App Bar**: Branding, hamburger trigger, search icon

### Tablet (768–991px)
- **Top App Bar** with hamburger trigger
- **Slide-out Drawer** for module navigation

### Desktop (≥ 992px)
- **Persistent Sidebar** (240 px) with all modules listed
- Active item highlighted with accent border

---

## Touch Gestures

The `TouchGestures` component wraps any content area and responds to:

| Gesture | Action |
|---|---|
| Swipe left | Next module / dismiss item |
| Swipe right | Previous module / open item |
| Swipe up | Scroll up |
| Swipe down | Pull-to-refresh (planned) |
| Pinch-to-zoom | Graph/image zoom (browser native) |

Gestures use a 50 px threshold to avoid false triggers during scrolling.

---

## Touch Targets

All interactive elements meet the **44 × 44 px minimum** touch target guideline (WCAG 2.5.5). This applies to:
- Navigation items
- Buttons and form controls
- List items and cards

---

## Safe Area Insets

The layout respects iOS/Android safe area insets using CSS `env()` variables:
- `env(safe-area-inset-top)` – notch/dynamic island
- `env(safe-area-inset-bottom)` – home indicator

---

## Haptic Feedback

The `navigator.vibrate()` API is used for subtle haptic feedback on:
- Successful actions (single short pulse)
- Errors (two short pulses)

---

## Camera Integration (Planned)

Future releases will add:
- QR code scanning for entity lookup (`/modules/digital-footprint?scan=qr`)
- Photo capture for evidence
- Document scanning for OCR ingestion
- Reverse image search upload

---

## Geolocation (Planned)

Future releases will add:
- GPS tagging for evidence items
- Map-based investigation visualization
- Nearby entity discovery

---

## Clipboard API

The **Paste** quick action in Cyber OSINT reads from the clipboard (`navigator.clipboard.readText()`) to auto-fill IP/domain lookup fields.

---

## Screen Wake Lock (Planned)

For long-running operations (bulk ingestion, large graph renders), the `WakeLock API` will prevent the device screen from sleeping.

---

## Module UI Adaptations

### Digital Footprint
- Tab bar: Email / Phone / Username / Social
- Large search input with scan FAB
- Results displayed as expandable mobile cards

### Investigation
- Swipeable case list (left = archive, right = open)
- FAB for new case creation

### Cyber OSINT
- Quick-action buttons: Paste from clipboard, Scan QR, Upload document
- Results as scrollable cards

### Misinformation
- Full-width text area for claim input
- Image upload for reverse image search
- Voice input support (planned)
