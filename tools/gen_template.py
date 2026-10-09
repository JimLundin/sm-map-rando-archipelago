"""
Write the YAML options template for the world (run from an Archipelago checkout containing the world):

    python /path/to/tools/gen_template.py <output directory>
"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.getcwd())
import ModuleUpdate  # noqa: E402

ModuleUpdate.update_ran = True
import Options  # noqa: E402
import worlds  # noqa: E402,F401

out_dir = sys.argv[1]
with tempfile.TemporaryDirectory() as tmp:
    Options.generate_yaml_templates(tmp, False)
    os.makedirs(out_dir, exist_ok=True)
    shutil.copy2(os.path.join(tmp, "Super Metroid Map Rando Upstream.yaml"), out_dir)
print(f"Wrote {out_dir}/Super Metroid Map Rando Upstream.yaml")
