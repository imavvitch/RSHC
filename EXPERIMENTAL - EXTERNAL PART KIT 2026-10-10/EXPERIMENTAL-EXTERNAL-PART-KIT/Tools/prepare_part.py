"""Step 2 (runs inside Unreal): checks the imported mesh, gives every material slot a material that can be cooked into
your pack, and writes the part definition (.rshcpart).

Material slots are what RSHC turns into colour sections. The slot NAME decides what happens in game:
  RSHC_tint_<id>   your own material; the player's colour goes into its RSHCColor parameter (textures stay)
  RSHC_own_<id>    RSHC paints the section with the game's hair shader in the player's colour
  RSHC_hair_<id>   follows the character's hair colour      RSHC_skin_<id>   follows the character's skin
  anything else    keeps its material; not recolourable
Morph targets on the mesh become 0..1 sliders by themselves.
"""
import json
import os
import sys
from pathlib import Path

import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit_common as kit  # noqa: E402

MEL = unreal.MaterialEditingLibrary
EAL = unreal.EditorAssetLibrary


def inside_pack(asset, root):
    return asset is not None and asset.get_path_name().startswith(root + '/')


def parent_chain(material):
    seen = []
    while material is not None and len(seen) < 16:
        seen.append(material)
        if isinstance(material, unreal.MaterialInstance):
            material = material.get_editor_property('parent')
        else:
            break
    return seen


def imported_look(material, root):
    """Base colour, base colour texture and normal texture of an imported material, where they can be found."""
    look = {'color': None, 'texture': None, 'normal': None}
    if material is None:
        return look
    try:
        for name in MEL.get_texture_parameter_names(material):
            text = str(name).lower()
            value = MEL.get_material_instance_texture_parameter_value(material, name) if isinstance(material, unreal.MaterialInstanceConstant) else None
            if value is None or not inside_pack(value, root):
                continue  # an engine placeholder, not a texture that came with the model
            if 'normal' in text and look['normal'] is None:
                look['normal'] = value
            elif ('basecolor' in text or 'diffuse' in text or 'albedo' in text) and look['texture'] is None:
                look['texture'] = value
        for name in MEL.get_vector_parameter_names(material):
            text = str(name).lower()
            if ('basecolor' in text or 'diffuse' in text) and isinstance(material, unreal.MaterialInstanceConstant):
                look['color'] = MEL.get_material_instance_vector_parameter_value(material, name)
                break
    except Exception as e:  # an importer that names things differently: the part still builds, in plain white
        unreal.log_warning('RSHC KIT could not read the imported material %s: %s' % (material.get_name(), e))
    return look


def make_material(c, name, look, style, tinted):
    path = c['root'] + '/' + name
    material = EAL.load_asset(path) if EAL.does_asset_exist(path) else None
    if material is None:
        material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, c['root'], unreal.Material, unreal.MaterialFactoryNew())
    kit.need(isinstance(material, unreal.Material), 'Could not create the material %s' % path)
    MEL.delete_all_material_expressions(material)
    material.set_editor_property('two_sided', c.get('twoSided', True) is not False)
    material.set_editor_property('used_with_skeletal_mesh', True)
    material.set_editor_property('used_with_morph_targets', True)
    material.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_UNLIT if style == 'unlit' else unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
    # RSHCColor is the one name RSHC writes the player's colour to. White leaves a texture as it was painted.
    color = MEL.create_material_expression(material, unreal.MaterialExpressionVectorParameter, -600, 0)
    color.set_editor_property('parameter_name', unreal.Name('RSHCColor'))
    start = unreal.LinearColor(1, 1, 1, 1)
    if look['color'] is not None and look['texture'] is None and not tinted:
        start = look['color']
    color.set_editor_property('default_value', start)
    output, pin = color, ''
    if look['texture'] is not None:
        sample = MEL.create_material_expression(material, unreal.MaterialExpressionTextureSampleParameter2D, -600, 250)
        sample.set_editor_property('parameter_name', unreal.Name('BaseTexture'))
        sample.set_editor_property('texture', look['texture'])
        multiply = MEL.create_material_expression(material, unreal.MaterialExpressionMultiply, -300, 100)
        MEL.connect_material_expressions(sample, 'RGB', multiply, 'A')
        MEL.connect_material_expressions(color, '', multiply, 'B')
        output, pin = multiply, ''
    MEL.connect_material_property(output, pin, unreal.MaterialProperty.MP_EMISSIVE_COLOR if style == 'unlit' else unreal.MaterialProperty.MP_BASE_COLOR)
    if style != 'unlit':
        rough = MEL.create_material_expression(material, unreal.MaterialExpressionScalarParameter, -300, 400)
        rough.set_editor_property('parameter_name', unreal.Name('Roughness'))
        rough.set_editor_property('default_value', float(c.get('roughness', 0.7)))
        MEL.connect_material_property(rough, '', unreal.MaterialProperty.MP_ROUGHNESS)
        if look['normal'] is not None:
            normal = MEL.create_material_expression(material, unreal.MaterialExpressionTextureSampleParameter2D, -600, 550)
            normal.set_editor_property('parameter_name', unreal.Name('NormalTexture'))
            normal.set_editor_property('texture', look['normal'])
            normal.set_editor_property('sampler_type', unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
            MEL.connect_material_property(normal, 'RGB', unreal.MaterialProperty.MP_NORMAL)
    MEL.recompile_material(material)
    EAL.save_loaded_asset(material, only_if_is_dirty=False)
    return material


def main():
    c = kit.config()
    out = kit.build_dir()
    # -SkipImport: the project is cooked as it was saved in Unreal; nothing is re-made.
    style = 'keep' if os.environ.get('RSHC_KIT_KEEP') else c['materials']
    meshes = []
    for path in EAL.list_assets(c['root'], recursive=True):
        asset = EAL.load_asset(path)
        if isinstance(asset, unreal.SkeletalMesh):
            meshes.append(asset)
    kit.need(meshes, 'No skeletal mesh under %s. Run the build without -SkipImport first.' % c['root'])
    wanted = c['modelPath'].stem
    named = [m for m in meshes if m.get_name() == wanted]
    kit.need(len(named) == 1 or len(meshes) == 1,
             'Found %d skeletal meshes under %s and none (or several) named %s. Put one mesh in the model file, or delete the '
             'old ones in UnrealProject/Content/Mods/%s.' % (len(meshes), c['root'], wanted, c['pack']))
    mesh = named[0] if len(named) == 1 else meshes[0]

    morphs = [str(m.get_name()) for m in mesh.get_editor_property('morph_targets')]
    for name in morphs:
        kit.need(len(name) <= 160 and name.replace('_', '').isalnum() and name.isascii(),
                 'Morph "%s": RSHC needs morph names made of letters, digits and _ only. Rename it in your modelling program.' % name)
    kit.need(len(morphs) <= 64, 'The mesh has %d morphs; RSHC shows at most 64 sliders per part.' % len(morphs))

    materials = mesh.get_editor_property('materials')
    kit.need(1 <= len(materials) <= 32, 'The mesh has %d material slots; 1 to 32 are supported.' % len(materials))
    slots, sections, used = [], [], set()
    for i, slot in enumerate(materials):
        slot_name = str(slot.get_editor_property('material_slot_name'))
        material = slot.get_editor_property('material_interface')
        mark = kit.MARK.match(slot_name)
        if not mark and material is not None and kit.MARK.match(material.get_name()):
            # The importer kept the name on the material only: carry it to the slot, which is what RSHC reads.
            slot_name = material.get_name()
            mark = kit.MARK.match(slot_name)
            slot.set_editor_property('material_slot_name', unreal.Name(slot_name))
        if slot_name.startswith('RSHC_') and not mark:
            raise kit.KitError('Material slot %d is named "%s". A recolourable slot must be RSHC_tint_<id>, RSHC_own_<id>, '
                               'RSHC_hair_<id> or RSHC_skin_<id>, with <id> in lowercase letters, digits and _.' % (i, slot_name))
        source, ident = (mark.group(1), mark.group(2)) if mark else (None, None)
        if mark:
            kit.need(len(ident) <= 24, 'Section ID "%s" is longer than 24 characters.' % ident)
            kit.need(ident not in used, 'Two material slots use the section ID "%s". Each section needs its own ID.' % ident)
            used.add(ident)
            sections.append((source, ident))
        chain = parent_chain(material)
        local = bool(chain) and all(inside_pack(m, c['root']) for m in chain)
        made = None
        if style == 'keep':
            kit.need(local, 'Material slot %d (%s): with "materials": "keep" every material and its parents must be saved '
                     'under %s, or the game cannot load them. This one is %s.' % (i, slot_name, c['root'], material.get_path_name() if material else 'empty'))
            base = chain[-1]
            kit.need(base.get_editor_property('used_with_skeletal_mesh'), 'Material %s: tick "Used with Skeletal Mesh" and save it.' % base.get_name())
            kit.need(not morphs or base.get_editor_property('used_with_morph_targets'), 'Material %s: tick "Used with Morph Targets" and save it.' % base.get_name())
            if source == 'tint':
                names = [str(n) for n in MEL.get_vector_parameter_names(material)]
                kit.need('RSHCColor' in names, 'Material %s is on the tint slot %s but has no Vector Parameter named RSHCColor, '
                         'so the in-game colour would do nothing.' % (material.get_name(), slot_name))
        else:
            tinted = source is not None
            made = make_material(c, 'M_%s_%s' % (c['pack'], ident or 'slot%d' % i), imported_look(material, c['root']), style, tinted)
            slot.set_editor_property('material_interface', made)
        materials[i] = slot
        final = made or material
        slots.append({'index': i, 'name': slot_name, 'section': ident, 'source': source, 'material': final.get_path_name()})
    kit.need(len(sections) <= 8, 'The mesh has %d marked colour sections; RSHC supports 8 per part.' % len(sections))
    mesh.set_editor_property('materials', materials)
    EAL.save_loaded_asset(mesh, only_if_is_dirty=False)

    mesh_path = mesh.get_path_name()
    text = kit.manifest_text(c, mesh_path, morphs, sections)
    file_name = c['pack'].lower() + '.rshcpart'
    (out / file_name).write_text(text, encoding='utf-8', newline='\n')
    package = mesh.get_outermost().get_name()            # /Game/Mods/<pack>/.../<Name>
    folder = package.rsplit('/', 1)[0]
    report = {'pack': c['pack'], 'id': c['id'], 'mesh': mesh_path, 'meshPackage': package,
              'cookDir': folder.replace('/Game/', '', 1), 'manifest': file_name, 'morphs': morphs, 'slots': slots,
              'sections': [{'id': i, 'source': s} for s, i in sections], 'materials': style}
    (out / 'part-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    unreal.log('RSHC KIT part ready: %s, %d morph slider(s), %d colour section(s)' % (mesh_path, len(morphs), len(sections)))


try:
    main()
except kit.KitError as e:
    unreal.log_error('RSHC KIT STOPPED: %s' % e)
    (Path(os.environ.get('RSHC_KIT_BUILD', '.')) / 'kit-error.txt').write_text(str(e), encoding='utf-8')
    raise SystemExit(1)
