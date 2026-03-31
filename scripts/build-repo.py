#!/usr/bin/env python3
"""
Build script for the WatchSocial Kodi repository.

Generates:
  dist/
    addons.xml          — index of all addons
    addons.xml.md5      — checksum for Kodi to detect updates
    plugin.watchsocial.sync/
      plugin.watchsocial.sync-{version}.zip
    repository.watchsocial/
      repository.watchsocial-{version}.zip

Run from the kodi-addon/ directory:
  python scripts/build-repo.py
"""

import hashlib
import os
import shutil
import xml.etree.ElementTree as ET
import zipfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
DIST_DIR = os.path.join(ROOT_DIR, "dist")

ADDON_DIRS = [
    "plugin.watchsocial.sync",
    "repository.watchsocial",
]


def get_addon_xml(addon_dir):
    path = os.path.join(ROOT_DIR, addon_dir, "addon.xml")
    if not os.path.exists(path):
        raise FileNotFoundError("Missing addon.xml in {}".format(addon_dir))
    return ET.parse(path)


def get_version(addon_dir):
    tree = get_addon_xml(addon_dir)
    return tree.getroot().attrib["version"]


def build_zip(addon_dir):
    """Create a zip of the addon directory."""
    addon_id = addon_dir
    version = get_version(addon_dir)
    zip_name = "{}-{}.zip".format(addon_id, version)

    out_dir = os.path.join(DIST_DIR, addon_id)
    os.makedirs(out_dir, exist_ok=True)
    zip_path = os.path.join(out_dir, zip_name)

    src_dir = os.path.join(ROOT_DIR, addon_dir)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for dirpath, dirnames, filenames in os.walk(src_dir):
            # Skip __pycache__ and .git
            dirnames[:] = [d for d in dirnames if d not in ("__pycache__", ".git")]
            for filename in filenames:
                if filename.endswith(".pyc"):
                    continue
                filepath = os.path.join(dirpath, filename)
                arcname = os.path.join(addon_id, os.path.relpath(filepath, src_dir))
                zf.write(filepath, arcname)

    print("  Built: {}".format(zip_path))
    return zip_path


def build_addons_xml():
    """Generate the addons.xml index file."""
    addons_el = ET.Element("addons")

    for addon_dir in ADDON_DIRS:
        tree = get_addon_xml(addon_dir)
        addon_el = tree.getroot()
        addons_el.append(addon_el)

    xml_path = os.path.join(DIST_DIR, "addons.xml")
    tree = ET.ElementTree(addons_el)
    ET.indent(tree, space="  ")
    tree.write(xml_path, encoding="utf-8", xml_declaration=True)
    print("  Built: {}".format(xml_path))

    # Generate MD5 checksum
    with open(xml_path, "rb") as f:
        md5 = hashlib.md5(f.read()).hexdigest()
    md5_path = xml_path + ".md5"
    with open(md5_path, "w") as f:
        f.write(md5)
    print("  Built: {}".format(md5_path))


def main():
    print("Building WatchSocial Kodi repository...")
    print()

    # Clean dist
    if os.path.exists(DIST_DIR):
        shutil.rmtree(DIST_DIR)
    os.makedirs(DIST_DIR)

    # Build zips
    print("Building addon zips:")
    for addon_dir in ADDON_DIRS:
        build_zip(addon_dir)
    print()

    # Build addons.xml
    print("Building addons.xml:")
    build_addons_xml()
    print()

    print("Done! Upload the contents of dist/ to your hosting.")
    print("Users add this source in Kodi:")
    print("  https://watchsocial.github.io/kodi-repo/")


if __name__ == "__main__":
    main()
