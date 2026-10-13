# UI and figure standards

## Visual direction

Use a light, restrained scientific interface with quiet neutral surfaces, dark
legible text, a single accent color, and ample space around the atomic viewport.
Element colors belong to scientific content; avoid using them as general UI accents.
Use native system typography and a consistent spacing scale, initially 4/8/12/16/24/32
logical pixels. Put colors, spacing, typography, borders, and radii in shared tokens.
Honor OS scaling and test macOS, Windows, and Linux where supported.

## Layout and interaction

Use a compact toolbar, a focused left panel for Structure/Composition/Appearance,
a large central viewport, and contextual selection details. Keep advanced options
progressively disclosed and basic tasks short. An empty state explains the first
action. Presets should be editable, and current units always visible.

Use aligned labels, predictable control sizes, concise tooltips, clear focus states,
keyboard navigation, selection counts, and undo/redo. Disable actions with an
explanation when they are unavailable. Validation belongs beside the affected input.
Never silently clamp scientifically meaningful values. Fit the initial slab well;
avoid resetting the user's camera after every composition edit.

## Figure standards

Default to orthographic projection, clean spherical atoms, subtle depth cues,
balanced margins, and no UI chrome. Lighting should clarify shape without hiding
element identity. Outlines, shadows, legends, and axes are optional and consistent.
Legends show element labels so meaning does not rely on color alone.

Use the same scene and camera for export preview and final output. Frame by the
visible atom extents including radii and enabled annotations, not position bounds
alone. Transparent exports must have clean antialiased edges without a white halo.
Text and line weights need deliberate physical-size handling in publication exports.

## Review checklist

- Pt (100) top, side, and tilted views are visually balanced and scientifically clear.
- Alloy element sizes and colors agree across viewport, legend, and exports.
- The smallest supported window and high-DPI displays have no clipped controls.
- Camera controls and atom picking remain understandable and responsive.
- PNG/TIFF render cleanly on light and dark backgrounds when transparent.
- PDF/SVG dimensions, text, outlines, and vector content survive reopening.
- Export preview matches the saved framing and optional annotations.
