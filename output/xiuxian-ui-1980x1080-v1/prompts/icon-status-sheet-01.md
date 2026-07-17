Task: generate a production-ready game UI `Icon_Status` asset sheet for automatic extraction.

Input image roles:
- Canonical UI Style Reference: use only to lock style, materials, palette, outlines, lighting, viewing angle, and polish.
- Layout Guide: use only for slot count, spacing, centering, and safe padding. Do not copy any visible guide line, label, color, box, or center mark.

Ordered assets, left-to-right and top-to-bottom:
1. CurrencyJade | state=Default | green jade currency medallion
2. CurrencyEssence | state=Default | blue swirling essence currency emblem
3. CurrencyVoucher | state=Default | red and pale-gold voucher currency emblem
4. PlayerLevelBadge | state=Default | small level badge frame with blank center
5. VipBadge | state=Default | small premium badge frame with blank center
6. BuffBadge | state=Default | small buff badge frame with blank center
7. QuestCompleted | state=Default | completed quest check seal without text
8. NotificationDot | state=Default | small red-gold notification dot

Layout contract:
- Canvas: 2048x2048
- Grid: 4 columns x 2 rows
- Exact asset count: 8
- One complete centered asset in each invisible slot
- Keep assets mutually separated by a large area of pure background
- No overlap, touching, clipping, cross-slot content, extra assets, or empty slots before the final requested asset
- Keep all outlines, corners, and allowed attached effects inside each safe box

Style:
Final game UI design canvas is exactly 1980x1080, Steam PC landscape. Create reusable UI bitmap assets proportioned for this screen, matching the approved canonical reference: clear high-key celestial blue and white jade, translucent ice-glass surfaces, thin silver-white filigree, restrained pale gold accents, front orthographic game UI presentation, crisp readable silhouettes, no text, no digits, no logos, no watermark, no characters, no scene background. The 2048x2048 production sheets are extraction canvases only, not the final interface size. Treat the canonical image only as visual identity, never copy its full layout or labels.
- Preserve one coherent UI family across every asset
- Keep details readable at mobile-game UI size

Background contract:
- Perfectly flat pure #FF00FF chroma-key background
- No gradient, texture, lighting variation, noise, reflection, floor, contact shadow, or cast shadow
- Do not use #FF00FF or visually similar colors inside any asset, outline, highlight, shadow, or effect

Forbidden:
- Text, numbers, labels, frame indices, logos, watermarks
- Checkerboard transparency, visible grids, separators, guide marks, or slot borders
- Scenery, environment, floor, reflections, presentation cards, or decorations between assets
- Cropped assets, merged assets, duplicated assets, or unrequested variants
- Do not add glow, aura, detached particles, floating effects, or shadows.

Before returning, reject the result unless the exact requested count, order, separation, complete silhouettes, flat chroma background, and canonical style are all correct.
