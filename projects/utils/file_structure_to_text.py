import os
from pathlib import Path

def generate_tree(startpath, output_file="tree_structure.md", for_read_me=False):
    lines = []

    def tree(dir_path, prefix=""):
        entries = sorted(os.listdir(dir_path))
        entries_count = len(entries)
        

        for index, entry in enumerate(entries):
            path = os.path.join(dir_path, entry)
            is_dir = os.path.isdir(path)
            connector = "└── " if index == entries_count - 1 else "├── "
            suffix = "/" if is_dir else ""
            # Skip __pycache__ folder
            if is_dir:
                # if entry in ["__pycache__",".git","old",".venv",".vscode",".history","gspy.egg-info"]:
                if entry.startswith(".") or entry == "__pycache__":
                    continue
            elif entry in ["file_structure_to_text.py",".gitignore"]:
                continue
            lines.append(prefix + connector + entry + suffix)
            if is_dir:
                if entry == "__pycache__":
                    extension = "    " if index == entries_count - 1 else "│   "
                    lines.append(prefix + extension + "└── ...")
                    continue

                extension = "    " if index == entries_count - 1 else "│   "
                tree(path, prefix + extension)

    # lines.append(f"{display_root}/")
    lines.append(f"{Path(startpath).name}/")
    tree(startpath)

    # save relative to script_dir
    output_path = startpath / output_file

    # add the '\' character to the end of the entry so that we have nice line endings when pasted in the README.md file
    line_ending = "\\\n" if for_read_me else "\n"
    line_start = "\\\n" if for_read_me else ""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(line_start + line_ending.join(lines))

    print(f"Tree structure saved to '{output_path}'")

# example for turboject demo projects
# generate_tree(Path(__file__).resolve().parent.parent.parent)            # complete GSPy root folder
# generate_tree(Path(__file__).resolve().parent.parent / "turbojet")    # turbojet project folder
# For developers:
generate_tree(Path(__file__).resolve().parent.parent / "turbojet", for_read_me=True)    # turbojet project folder for pasting in README.md file, with '\' at the end of each line for nice line endings
# generate_tree(Path(__file__).resolve().parent.parent / "turbofan")    # turbofan project folder
