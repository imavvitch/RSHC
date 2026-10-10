"""Shared by the kit's Unreal scripts: reads part.json and applies RSHC's rules for a part definition.

The rules below mirror RSHC's own reader (Scripts/part_slots.lua). A definition that passes here is accepted by the game;
whether the part looks right is for you to check in game.
"""
import json
import os
import re
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
MARK = re.compile(r'^RSHC_(tint|own|skin|hair)_([a-z][a-z0-9_]*)$')


class KitError(Exception):
    pass


def need(condition, message):
    if not condition:
        raise KitError(message)


def config():
    path = KIT / 'part.json'
    need(path.is_file(), 'part.json is missing from the kit folder')
    try:
        c = json.loads(path.read_text(encoding='utf-8-sig'))
    except ValueError as e:
        raise KitError('part.json is not valid JSON: %s' % e)
    need(isinstance(c, dict), 'part.json must be one { ... } object')
    for key in ('pack', 'model', 'id'):
        need(isinstance(c.get(key), str) and c[key], 'part.json: "%s" is required' % key)
    need(re.match(r'^[A-Za-z][A-Za-z0-9]{2,23}$', c['pack']),
         'part.json: "pack" must be 3 to 24 letters or digits, starting with a letter (it becomes a folder and file name)')
    model = (KIT / c['model']).resolve()
    need(model.is_file(), 'part.json: model file not found: %s' % model)
    need(model.suffix.lower() in ('.glb', '.gltf', '.fbx'), 'part.json: "model" must be a .glb, .gltf or .fbx file')
    c['modelPath'] = model
    c.setdefault('materials', 'lit')
    need(c['materials'] in ('lit', 'unlit', 'keep'), 'part.json: "materials" must be "lit", "unlit" or "keep"')
    c.setdefault('extraLines', [])
    need(isinstance(c['extraLines'], list) and all(isinstance(x, str) for x in c['extraLines']),
         'part.json: "extraLines" must be a list of text lines')
    c['root'] = '/Game/Mods/' + c['pack']
    return c


def build_dir():
    value = os.environ.get('RSHC_KIT_BUILD')
    need(value, 'RSHC_KIT_BUILD is not set; run Tools/Build-Part.ps1 instead of this script')
    path = Path(value)
    path.mkdir(parents=True, exist_ok=True)
    return path


# ---- the part definition (.rshcpart)

def _slot_ok(s):
    return isinstance(s, str) and len(s) <= 24 and re.match(r'^[a-z][a-z0-9_]*$', s) is not None


def _label_ok(s):
    return isinstance(s, str) and 0 < len(s) <= 40 and re.match(r'^[A-Za-z0-9 _\-]+$', s) is not None


def _path_ok(s):
    return isinstance(s, str) and len(s) <= 240 and re.match(r'^/Game/[A-Za-z0-9_/.]+$', s) is not None and '..' not in s


def _number(text):
    try:
        value = float(text)
    except ValueError:
        return None
    return value if value == value and abs(value) != float('inf') else None


def check_slider(key, value):
    ident = key[len('slider.'):]
    need(_slot_ok(ident), '%s: the slider ID must be lowercase letters, digits and _ (max 24), starting with a letter' % key)
    fields = value.split('|')
    need(len(fields) in (8, 9), '%s: expected Label|group|binding|target|min|max|default|step[|section]' % key)
    label, group, binding, target = fields[:4]
    lo, hi, default, step = (_number(x) for x in fields[4:8])
    need(_label_ok(label), '%s: label must be 1 to 40 letters, digits, spaces, _ or -' % key)
    need(group in ('color', 'physical', 'misc'), '%s: group must be color, physical or misc' % key)
    need(None not in (lo, hi, default, step) and abs(lo) <= 100000 and abs(hi) <= 100000 and lo < hi
         and lo <= default <= hi and 0 < step <= hi - lo, '%s: min < max, default inside them, step above 0' % key)
    if binding in ('scale', 'offset', 'rotation'):
        need(group == 'physical' and (target in ('x', 'y', 'z') or (binding == 'scale' and target == 'all')),
             '%s: %s needs group physical and target x, y or z%s' % (key, binding, ' (or all)' if binding == 'scale' else ''))
        need(binding != 'scale' or lo > 0, '%s: a scale slider must stay above 0' % key)
    elif binding == 'morph':
        need(group == 'physical' and len(target) <= 160 and re.match(r'^[A-Za-z0-9_]+$', target) and lo >= -1 and hi <= 1,
             '%s: morph needs group physical, a morph name of letters, digits and _, and a range within -1..1' % key)
    elif binding == 'scalar':
        need(re.match(r'^\d+:[A-Za-z0-9_]+$', target) and int(target.split(':')[0]) <= 31,
             '%s: scalar target is materialSlotNumber:ParameterName' % key)
    elif binding == 'primitive':
        n = _number(target)
        need(n is not None and n == int(n) and 0 <= n <= 63, '%s: primitive target is a whole number 0..63' % key)
    else:
        raise KitError('%s: binding must be morph, scale, offset, rotation, scalar or primitive' % key)
    need(len(fields) == 8 or _slot_ok(fields[8]), '%s: the section ID at the end is not valid' % key)
    return ident, binding, target


def manifest_text(c, mesh_path, morphs, sections):
    """c: config; mesh_path: /Game/.../Name.Name; morphs: names on the mesh; sections: [(source, id)] found on its slots."""
    need(isinstance(c['id'], str) and len(c['id']) <= 64 and re.match(r'^[A-Za-z0-9_\-]+:[A-Za-z0-9_\-]+$', c['id']),
         'part.json: "id" must look like yourname:part_name (letters, digits, _ and -, max 64)')
    need(c['id'] != 'rshc:vanilla', 'part.json: rshc:vanilla is reserved')
    need(_path_ok(mesh_path), 'The mesh path is not usable by RSHC (letters, digits, _ / . only, max 240): %s' % mesh_path)
    slot = c.get('slot') or 'uncategorized'
    need(_slot_ok(slot), 'part.json: "slot" must be lowercase letters, digits and _ (max 24), starting with a letter')
    need(slot not in ('brows', 'beard', 'skin', 'face', 'eyes', 'body'),
         'part.json: the slot "%s" is reserved by RSHC (body replacements are not built by this kit)' % slot)
    lines = ['# Made with the RSHC Asset Kit (experimental).', 'schema=1', 'id=' + c['id'], 'slot=' + slot]
    for key in ('slotLabel', 'label'):
        if c.get(key):
            need(_label_ok(c[key]), 'part.json: "%s" must be 1 to 40 letters, digits, spaces, _ or -' % key)
            lines.append('%s=%s' % (key, c[key]))
    lines.append('mesh=' + mesh_path)
    socket, anchor = c.get('socket'), c.get('anchor')
    need(isinstance(socket, str) and len(socket) <= 64 and re.match(r'^[A-Za-z0-9_]+$', socket) and socket != 'None',
         'part.json: "socket" is required: the bone or socket of the character the part hangs on (for example pelvis or head)')
    need(anchor in (None, 'body', 'head'), 'part.json: "anchor" must be "body" or "head"')
    lines.append('socket=' + socket)
    if anchor == 'head':
        lines.append('anchor=head')
    seen = set()
    declared_morphs = set()
    for raw in c['extraLines']:
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        m = re.match(r'^([A-Za-z0-9_.]+)\s*=\s*(.*?)\s*$', line)
        need(m, 'part.json extraLines: not a key=value line: %s' % raw)
        key, value = m.groups()
        need(key.startswith('slider.') or key == 'autoMorphs',
             'part.json extraLines: only slider.<id>=... lines and autoMorphs=false are supported here: %s' % raw)
        if key == 'autoMorphs':
            need(value in ('true', 'false'), 'autoMorphs must be true or false')
        else:
            ident, binding, target = check_slider(key, value)
            need(ident not in seen, 'part.json extraLines: slider ID used twice: %s' % ident)
            seen.add(ident)
            if binding == 'morph':
                need(target in morphs, 'part.json extraLines: %s names the morph "%s", which the mesh does not have (it has: %s)'
                     % (key, target, ', '.join(morphs) or 'none'))
                declared_morphs.add(target)
            fields = value.split('|')
            need(len(fields) == 8, '%s: a section ID at the end only works with section.N lines, which this kit does not write; remove it' % key)
        lines.append('%s=%s' % (key, value))
    need(len(seen) + len([m for m in morphs if m not in declared_morphs]) <= 64, 'More than 64 sliders on one part')
    need(len([s for s in sections]) <= 8, 'More than 8 colour sections on one part')
    text = '\n'.join(lines) + '\n'
    need(len(text) <= 32768, 'The part definition is too large')
    return text
