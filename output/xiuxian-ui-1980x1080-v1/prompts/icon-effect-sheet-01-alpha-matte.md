Use case: precise-object-edit
Asset type: grayscale opacity matte for a game UI `Icon_Effect` production sheet
Primary request: convert the attached color-source sheet into a pixel-aligned grayscale opacity matte without changing any silhouette, position, scale, spacing, or canvas dimensions.

Ordered assets, left-to-right and top-to-bottom:
1. SoftBlueGlow | state=Default
2. GoldSelectedGlow | state=Default
3. StarSparkle | state=Default
4. NotificationPulse | state=Default

Layout invariants:
- Grid: 2 columns x 2 rows
- Exact asset count: 4
- Preserve the exact geometry and placement of every attached effect

Matte encoding:
- Pure black means fully transparent
- Pure white means fully opaque
- Gray levels encode partial opacity
- Smoke tails, glass interiors, liquid films, droplets, soft glows, and antialiased edges must use continuous gray gradients
- Background must be uniform pure black

Forbidden:
- Color, checkerboard, text, labels, borders, shadows, added particles, moved elements, resized elements, altered silhouettes, or any decorative background
- Do not redesign the effects; output only their aligned opacity information
