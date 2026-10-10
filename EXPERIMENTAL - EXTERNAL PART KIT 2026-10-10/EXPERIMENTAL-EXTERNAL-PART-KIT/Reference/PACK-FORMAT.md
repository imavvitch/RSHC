# RSHC part packs

Install mesh/material assets in the game alongside a `.rshcpart` data manifest in this directory. Every peer needs the same assets and pack manifests; the exchange carries selections and settings, not asset files or executable code.

The editor follows this hierarchy:

Slot/category -> selected part -> special options -> optional sections -> texture/color and physical controls.

`slot` is a stable lowercase machine key. `slotLabel` is its display label. An unknown slot such as `wings` creates a category automatically. `hair` adds choices to Hair alongside native styles. Use the same slot label across packs. `id` must be a globally unique `author:part` ID; keep IDs stable across releases. Native parts synchronize by row name, so differing catalog order does not change the selected style.

A manifest uses `schema=1`, `kind=skeletal_attachment`, `binding=leader_pose`, `anchor=head` or `body`, a display `label`, and one or more `variant.<source mesh name>=/Game/.../Asset.Asset` mappings. The pack mesh must use the source skeleton. Body attachments follow BodyMesh; head attachments follow HeadMesh. `flattenHead=true` is optional and only valid for head attachments; Ears default to it, other slots do not.

`color=none` retains the asset materials with no coloring sections. `color=skin` provides a Skin section. `color=sections` declares contiguous material slots starting at zero:

```
section.0=feathers|Feathers|own|AAF0CC
section.1=trim|Trim|skin
```

The source can be `own`, `skin`, or `hair`. Own overrides remain independent and are saved/exchanged. Section IDs must be stable lowercase keys. `material.<source mesh name>=1` chooses the source material when borrowing skin.

Declare multiple sliders with stable IDs:

```
slider.effect=Effect|misc|primitive|4|0|1|0|0.1
slider.glow=Glow|color|scalar|0:Glow|0|20|0|0.1|feathers
slider.size=Size|physical|scale|all|0.5|2|1|0.01
slider.spread=Spread|physical|rotation|z|-45|45|0|1
```

Format: `slider.<id>=Label|group|binding|target|min|max|default|step[|section ID]`.

- `misc`: special sliders in Parts above the notes.
- `color`: texture/color sliders in the Color panel's existing slider area.
- `physical`: sliders in Size Sliders below the standard proportions.

An optional section ID scopes the displayed color/physical controls to that selected section. Special controls remain visible for the selected part. Omit the section for whole-part controls.

Supported bindings: `scale` (positive, x/y/z/all), `offset` (x/y/z, centimeters), `rotation` (x/y/z, degrees), `scalar` (material-slot:parameter-name), and `primitive` (custom primitive float index 0..63). Transform bindings adjust the whole attachment. Material scalar controls create a private dynamic material, preserving other parts' colors. Material parameters and primitive indices must exist and be used by your assets; declaring a name does not add a shader feature. Arbitrary functions and Lua are not supported.

Selections, section HEX values, and all declared slider values save with Save and travel in every complete appearance exchange. Missing-pack IDs/settings are retained in profiles and relayed snapshots, allowing the same selection to recover after the pack is installed. There is no idle network polling; edits, joins, appearance changes, and explicit requests trigger exchange.

Bounds: 64 sliders per part, 256 saved custom values per character, 64 part slots and 64 coloring sections per snapshot, and an 8 KiB appearance payload. Oversized/invalid data is rejected rather than silently dropped. Keep packs within those combined budgets.
