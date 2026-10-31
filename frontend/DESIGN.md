# CivicMesh app design

The approved brand overrides generic palette defaults: parchment `#faf5ec`, cream `#fffdf9`, brown ink `#3c2b20`, burnt orange `#be501c`, golden Report action `#f6c25b`, muted earth-toned semantic indicators. Nunito is self-hosted with its OFL license.

Operate-mode screens use a quiet tinted frame, readable forms and distinct map/list regions. Rounded irregular corners, the drawn brand underline, organic marker outlines and warm colors carry the illustration identity without putting the landing scene behind app data. Icons remain simple functional SVG paths. Status includes words, never color alone.

Mobile has exactly Map / Report / Campaigns bottom destinations, a central plus and top-right profile. At desktop widths navigation becomes a left sidebar. No Home or hamburger. Map/list switching is local view state, not an extra destination.

No continuous animation. Reduced-motion respects browser/Leaflet settings. All primary controls have visible focus; app targets are at least 44px. Maps offer issue lists or coordinate entry as keyboard alternatives. No browser zoom restriction.

Validation: build and Playwright cover core cross-screen data flow, local media persistence, evidence privacy, support/undo, GPS success/denial, map tile recovery and 390/768/1440 layouts. Public map tiles are replaced by fixtures during automated interaction tests.
