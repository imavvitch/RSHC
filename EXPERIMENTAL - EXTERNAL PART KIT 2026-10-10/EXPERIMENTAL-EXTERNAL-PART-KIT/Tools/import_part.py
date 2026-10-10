"""Step 1 (runs inside Unreal): imports the model named in part.json into /Game/Mods/<pack>."""
import json
import sys
from pathlib import Path

import unreal

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit_common as kit  # noqa: E402


def main():
    c = kit.config()
    out = kit.build_dir()
    name = c['modelPath'].stem
    kit.need(name.replace('_', '').isalnum() and len(name) <= 40,
             'The model file name must be letters, digits and _ only, 40 characters at most: %s' % c['modelPath'].name)
    task = unreal.AssetImportTask()
    task.filename = str(c['modelPath'])
    task.destination_path = c['root']
    task.destination_name = name
    task.automated = True
    task.replace_existing = True
    task.save = True
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    rows = []
    for path in unreal.EditorAssetLibrary.list_assets(c['root'], recursive=True):
        asset = unreal.EditorAssetLibrary.load_asset(path)
        if asset:
            rows.append({'path': path, 'class': asset.get_class().get_name()})
    meshes = [r for r in rows if r['class'] == 'SkeletalMesh']
    kit.need(meshes, 'Unreal imported no skeletal mesh from %s. The model needs a skeleton (at least one bone) and skin '
             'weights; a static mesh cannot carry sliders.' % c['modelPath'].name)
    (out / 'import-report.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
    unreal.log('RSHC KIT import: %d assets, skeletal meshes: %s' % (len(rows), ', '.join(m['path'] for m in meshes)))


try:
    main()
except kit.KitError as e:
    unreal.log_error('RSHC KIT STOPPED: %s' % e)
    (Path(__import__('os').environ.get('RSHC_KIT_BUILD', '.')) / 'kit-error.txt').write_text(str(e), encoding='utf-8')
    raise SystemExit(1)
