*.part.json    Ready-made settings for two common cases. Copy one over part.json in the kit folder, put your own
               model in Source, and change the names. The models named in them are not included.

*.rshcpart     Part definitions written by hand for the kinds of part this kit does NOT build: parts that bend
               with the face or body (they must use the game's own skeleton, one variant per head or body) and
               parts with sections and sliders declared line by line. PACK-FORMAT.md explains every line.
               The asset paths in them are placeholders.

The model for "horns-on-head" has one morph target named HornCurl; the last line of its extraLines gives that
morph its own label, range and starting value instead of the automatic 0 to 1 slider.

existing-mod-item.rshcpart, existing-mod-body.rshcpart
               For a mesh you have ALREADY cooked and packed yourself: the one small file that lists it in RSHC.
               No build with this kit is needed. Section 9 of START-HERE.html explains each line.
