Task: generate a production-ready game UI `Button` asset sheet for automatic extraction.

Input image roles:
- Canonical UI Style Reference: use only to lock style, materials, palette, outlines, lighting, viewing angle, and polish.
- Layout Guide: use only for slot count, spacing, centering, and safe padding. Do not copy any visible guide line, label, color, box, or center mark.

Ordered assets, left-to-right and top-to-bottom:
1. QuestTab | state=Normal | shallow tab button, blank center
2. QuestTab | state=Hover | same exact tab, brighter hover rim
3. QuestTab | state=Pressed | same exact tab, selected pressed appearance
4. QuestTab | state=Disabled | same exact tab, desaturated disabled
5. QuestComplete | state=Normal | small ornamental action button, blank center
6. QuestComplete | state=Hover | same exact button, brighter hover rim
7. QuestComplete | state=Pressed | same exact button, visibly pressed
8. QuestComplete | state=Disabled | same exact button, desaturated disabled
9. QuestCompleteAll | state=Normal | wide primary ornamental action button, blank center
10. QuestCompleteAll | state=Hover | same exact button, brighter hover rim
11. QuestCompleteAll | state=Pressed | same exact button, visibly pressed
12. QuestCompleteAll | state=Disabled | same exact button, desaturated disabled

Layout contract:
- Canvas: 2048x2048
- Grid: 4 columns x 3 rows
- Exact asset count: 12
- One complete centered asset in each invisible slot
- Keep assets mutually separated by a large area of pure background
- No overlap, touching, clipping, cross-slot content, extra assets, or empty slots before the final requested asset
- Keep all outlines, corners, and allowed attached effects inside each safe box

Style:
Final game UI design canvas is exactly 1980x1080, Steam PC landscape. Create reusable UI bitmap assets proportioned for this screen, matching the approved canonical reference: clear high-key celestial blue and white jade, translucent ice-glass surfaces, thin silver-white filigree, restrained pale gold accents, front orthographic game UI presentation, crisp readable silhouettes, no text, no digits, no logos, no watermark, no characters, no scene background. The 2048x2048 production sheets are extraction canvases only, not the final interface size. Treat the canonical image only as visual identity, never copy its full layout or labels.
- Preserve one coherent UI family across every asset
- Keep details readable at mobile-game UI size

Background contract:
- Perfectly flat pure #00FF00 chroma-key background
- No gradient, texture, lighting variation, noise, reflection, floor, contact shadow, or cast shadow
- Do not use #00FF00 or visually similar colors inside any asset, outline, highlight, shadow, or effect

Forbidden:
- Text, numbers, labels, frame indices, logos, watermarks
- Checkerboard transparency, visible grids, separators, guide marks, or slot borders
- Scenery, environment, floor, reflections, presentation cards, or decorations between assets
- Cropped assets, merged assets, duplicated assets, or unrequested variants
- Do not add glow, aura, detached particles, floating effects, or shadows.

Before returning, reject the result unless the exact requested count, order, separation, complete silhouettes, flat chroma background, and canonical style are all correct.
