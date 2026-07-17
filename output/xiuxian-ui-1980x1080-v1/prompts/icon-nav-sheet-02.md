Task: generate a production-ready game UI `Icon_Nav` asset sheet for automatic extraction.

Input image roles:
- Canonical UI Style Reference: use only to lock style, materials, palette, outlines, lighting, viewing angle, and polish.
- Layout Guide: use only for slot count, spacing, centering, and safe padding. Do not copy any visible guide line, label, color, box, or center mark.

Ordered assets, left-to-right and top-to-bottom:
1. ActivityDrum | state=Default | ornamental war drum
2. ActivityAchievement | state=Default | achievement medal and check seal
3. ActivityAlliance | state=Default | alliance handshake emblem
4. ActivityBanner | state=Default | small celestial battle banner
5. ActivityRanking | state=Default | three-level ranking podium
6. FunctionPavilion | state=Default | celestial pavilion building
7. FunctionTreasure | state=Default | crystal treasure chest
8. FunctionTalisman | state=Default | round coin talisman with tassel
9. FunctionShop | state=Default | small xianxia shop building
10. FunctionScroll | state=Default | rolled quest scroll with blue seal
11. FunctionWealth | state=Default | fortune pouch and coins
12. FunctionCompanion | state=Default | paired companion silhouettes, no facial detail
13. FunctionCharacter | state=Default | single cultivator silhouette bust, no facial detail

Layout contract:
- Canvas: 2048x2048
- Grid: 4 columns x 4 rows
- Exact asset count: 13
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
