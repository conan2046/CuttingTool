Task: generate a production-ready game UI `Icon_Effect` asset sheet for automatic extraction.

Input image roles:
- Canonical UI Style Reference: use only to lock style, materials, palette, outlines, lighting, viewing angle, and polish.
- Layout Guide: use only for slot count, spacing, centering, and safe padding. Do not copy any visible guide line, label, color, box, or center mark.

Ordered assets, left-to-right and top-to-bottom:
1. SoftBlueGlow | state=Default | soft circular cool blue aura with smooth falloff
2. GoldSelectedGlow | state=Default | restrained pale gold selection halo with smooth falloff
3. StarSparkle | state=Default | delicate white-blue celestial star sparkle cluster
4. NotificationPulse | state=Default | small red-gold circular pulse ring with smooth falloff

Layout contract:
- Canvas: 2048x2048
- Grid: 2 columns x 2 rows
- Exact asset count: 4
- One complete centered asset in each invisible slot
- Keep assets mutually separated by a large area of pure background
- No overlap, touching, clipping, cross-slot content, extra assets, or empty slots before the final requested asset
- Keep all outlines, corners, and allowed attached effects inside each safe box

Style:
Final game UI design canvas is exactly 1980x1080, Steam PC landscape. Create reusable UI bitmap assets proportioned for this screen, matching the approved canonical reference: clear high-key celestial blue and white jade, translucent ice-glass surfaces, thin silver-white filigree, restrained pale gold accents, front orthographic game UI presentation, crisp readable silhouettes, no text, no digits, no logos, no watermark, no characters, no scene background. The 2048x2048 production sheets are extraction canvases only, not the final interface size. Treat the canonical image only as visual identity, never copy its full layout or labels.
- Preserve one coherent UI family across every asset
- Keep details readable at mobile-game UI size

Model-matte color contract:
- Render every requested effect over one perfectly flat pure black RGB background
- Preserve translucent-looking interiors, smoke density, glass highlights, liquid films, and glow falloff in color
- No checkerboard, scene, floor, cast shadow, presentation card, gradient backdrop, or opaque frame
- This is the color source; a separate grayscale opacity matte will be generated from it

Forbidden:
- Text, numbers, labels, frame indices, logos, watermarks
- Checkerboard transparency, visible grids, separators, guide marks, or slot borders
- Scenery, environment, floor, reflections, presentation cards, or decorations between assets
- Cropped assets, merged assets, duplicated assets, or unrequested variants
- Do not add glow, aura, detached particles, floating effects, or shadows.

Before returning, reject the result unless the exact requested count, order, separation, complete silhouettes, flat black color-source background, and canonical style are all correct.
