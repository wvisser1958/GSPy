#!/usr/bin/env python3
"""
class_diagram.py

Create a text-based class inheritance diagram for all .py files in a folder.

Example:
    python class_diagram.py /path/to/project
    python class_diagram.py /path/to/project --recursive
    python class_diagram.py /path/to/project --classesonly
    python class_diagram.py /path/to/project --output diagram.txt
    python .\class_hierarchy.py ..\..\src\gspy\core\ --output diagram.txt --classesonly
    python .\projects\file_utils\class_hierarchy.py .\src\gspy\core\ --output .\projects\file_utils\diagram.txt
"""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set


@dataclass
class MethodInfo:
    name: str
    is_static: bool = False
    is_classmethod: bool = False
    is_property: bool = False
    is_private: bool = False


@dataclass
class ClassInfo:
    name: str
    module: str
    file_path: Path
    bases: List[str] = field(default_factory=list)
    class_vars: List[str] = field(default_factory=list)
    methods: List[MethodInfo] = field(default_factory=list)

    @property
    def full_name(self) -> str:
        return f"{self.module}.{self.name}" if self.module else self.name


class PythonClassVisitor(ast.NodeVisitor):
    def __init__(self, module_name: str, file_path: Path) -> None:
        self.module_name = module_name
        self.file_path = file_path
        self.classes: List[ClassInfo] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        class_info = ClassInfo(
            name=node.name,
            module=self.module_name,
            file_path=self.file_path,
            bases=[self._expr_to_name(base) for base in node.bases],
        )

        for stmt in node.body:
            if isinstance(stmt, (ast.Assign, ast.AnnAssign)):
                class_vars = self._extract_class_vars(stmt)
                class_info.class_vars.extend(class_vars)

            elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                class_info.methods.append(self._extract_method_info(stmt))

        self.classes.append(class_info)
        self.generic_visit(node)

    def _extract_class_vars(self, stmt: ast.stmt) -> List[str]:
        names: List[str] = []

        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                names.extend(self._extract_target_names(target))

        elif isinstance(stmt, ast.AnnAssign):
            names.extend(self._extract_target_names(stmt.target))

        return names

    def _extract_target_names(self, target: ast.AST) -> List[str]:
        if isinstance(target, ast.Name):
            return [target.id]
        if isinstance(target, ast.Tuple):
            names: List[str] = []
            for elt in target.elts:
                names.extend(self._extract_target_names(elt))
            return names
        return []

    def _extract_method_info(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> MethodInfo:
        decorator_names = {self._expr_to_name(dec) for dec in node.decorator_list}

        return MethodInfo(
            name=node.name,
            is_static="staticmethod" in decorator_names,
            is_classmethod="classmethod" in decorator_names,
            is_property="property" in decorator_names or any(
                dec.endswith(".setter") or dec.endswith(".getter") or dec.endswith(".deleter")
                for dec in decorator_names
            ),
            is_private=node.name.startswith("_") and not node.name.startswith("__"),
        )

    def _expr_to_name(self, expr: ast.AST) -> str:
        if isinstance(expr, ast.Name):
            return expr.id
        if isinstance(expr, ast.Attribute):
            left = self._expr_to_name(expr.value)
            return f"{left}.{expr.attr}" if left else expr.attr
        if isinstance(expr, ast.Subscript):
            return self._expr_to_name(expr.value)
        if isinstance(expr, ast.Call):
            return self._expr_to_name(expr.func)
        if isinstance(expr, ast.Constant):
            return repr(expr.value)
        return "<unknown>"


def path_to_module(root: Path, file_path: Path) -> str:
    relative = file_path.relative_to(root)
    parts = list(relative.parts)

    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1].rsplit(".", 1)[0]

    return ".".join(parts)


def collect_python_files(folder: Path, recursive: bool) -> List[Path]:
    pattern = "**/*.py" if recursive else "*.py"
    return sorted(p for p in folder.glob(pattern) if p.is_file())


def parse_classes(root: Path, files: List[Path]) -> Dict[str, ClassInfo]:
    classes: Dict[str, ClassInfo] = {}

    for file_path in files:
        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(file_path))
        except Exception as exc:
            print(f"[WARN] Could not parse {file_path}: {exc}")
            continue

        module_name = path_to_module(root, file_path)
        visitor = PythonClassVisitor(module_name=module_name, file_path=file_path)
        visitor.visit(tree)

        for cls in visitor.classes:
            classes[cls.full_name] = cls

    return classes


def build_inheritance_maps(classes: Dict[str, ClassInfo]) -> tuple[Dict[str, List[str]], Dict[str, Set[str]]]:
    children_map: Dict[str, List[str]] = {name: [] for name in classes}
    unresolved_bases_map: Dict[str, Set[str]] = {name: set() for name in classes}

    simple_name_map: Dict[str, List[str]] = {}
    for full_name, cls in classes.items():
        simple_name_map.setdefault(cls.name, []).append(full_name)

    for child_full_name, cls in classes.items():
        for base in cls.bases:
            matched_parent: Optional[str] = None

            if base in classes:
                matched_parent = base
            elif base in simple_name_map and len(simple_name_map[base]) == 1:
                matched_parent = simple_name_map[base][0]
            else:
                local_candidate = f"{cls.module}.{base}" if cls.module else base
                if local_candidate in classes:
                    matched_parent = local_candidate

            if matched_parent:
                children_map[matched_parent].append(child_full_name)
            else:
                unresolved_bases_map[child_full_name].add(base)

    for parent in children_map:
        children_map[parent].sort()

    return children_map, unresolved_bases_map


def method_label(method: MethodInfo) -> str:
    tags: List[str] = []
    if method.is_static:
        tags.append("static")
    if method.is_classmethod:
        tags.append("classmethod")
    if method.is_property:
        tags.append("property")
    if method.is_private:
        tags.append("private")

    if tags:
        return f"{method.name}() [{' ,'.join(tags)}]".replace(" ,", ", ")
    return f"{method.name}()"


def render_class_block(
    class_name: str,
    classes: Dict[str, ClassInfo],
    children_map: Dict[str, List[str]],
    unresolved_bases_map: Dict[str, Set[str]],
    include_private: bool,
    classes_only: bool,
    prefix: str = "",
    is_last: bool = True,
    visited: Optional[Set[str]] = None,
) -> List[str]:
    if visited is None:
        visited = set()

    lines: List[str] = []

    if class_name in visited:
        connector = "└── " if is_last else "├── "
        lines.append(f"{prefix}{connector}{classes[class_name].name} [already shown]")
        return lines

    visited.add(class_name)
    cls = classes[class_name]

    connector = "└── " if is_last else "├── "
    line = f"{prefix}{connector}{cls.name}"

    unresolved = sorted(unresolved_bases_map[class_name])
    if unresolved:
        line += f"  (external base: {', '.join(unresolved)})"

    lines.append(line)

    child_prefix = prefix + ("    " if is_last else "│   ")

    if not classes_only:
        shown_vars = [v for v in cls.class_vars if include_private or not v.startswith("_")]
        shown_methods = [m for m in cls.methods if include_private or not m.name.startswith("_")]

        if shown_vars:
            lines.append(f"{child_prefix}├── class variables")
            for i, var_name in enumerate(shown_vars):
                sub_connector = "└── " if i == len(shown_vars) - 1 else "├── "
                lines.append(f"{child_prefix}│   {sub_connector}{var_name}")

        if shown_methods:
            lines.append(f"{child_prefix}├── methods")
            for i, method in enumerate(shown_methods):
                sub_connector = "└── " if i == len(shown_methods) - 1 else "├── "
                lines.append(f"{child_prefix}│   {sub_connector}{method_label(method)}")

    children = children_map[class_name]
    if children:
        if classes_only:
            for i, child_name in enumerate(children):
                child_is_last = i == len(children) - 1
                lines.extend(
                    render_class_block(
                        child_name,
                        classes,
                        children_map,
                        unresolved_bases_map,
                        include_private,
                        classes_only,
                        prefix=child_prefix,
                        is_last=child_is_last,
                        visited=visited,
                    )
                )
        else:
            lines.append(f"{child_prefix}└── subclasses")
            for i, child_name in enumerate(children):
                child_is_last = i == len(children) - 1
                lines.extend(
                    render_class_block(
                        child_name,
                        classes,
                        children_map,
                        unresolved_bases_map,
                        include_private,
                        classes_only,
                        prefix=child_prefix + "    ",
                        is_last=child_is_last,
                        visited=visited,
                    )
                )

    return lines


def collect_reachable(node: str, children_map: Dict[str, List[str]], visited: Set[str]) -> None:
    if node in visited:
        return
    visited.add(node)
    for child in children_map.get(node, []):
        collect_reachable(child, children_map, visited)


def render_diagram(classes: Dict[str, ClassInfo], include_private: bool, classes_only: bool) -> str:
    if not classes:
        return "No classes found."

    children_map, unresolved_bases_map = build_inheritance_maps(classes)
    all_children = {child for children in children_map.values() for child in children}

    roots = []
    for full_name, cls in classes.items():
        has_internal_parent = full_name in all_children
        if not has_internal_parent:
            roots.append(full_name)

    roots.sort(key=lambda name: (classes[name].file_path.as_posix(), classes[name].name))

    lines: List[str] = []
    lines.append("Class inheritance diagram")
    lines.append("=" * 25)

    grouped_roots: Dict[Path, List[str]] = {}
    for root in roots:
        grouped_roots.setdefault(classes[root].file_path, []).append(root)

    for file_index, file_path in enumerate(sorted(grouped_roots)):
        if file_index > 0:
            lines.append("")

        lines.append(str(file_path))
        file_roots = grouped_roots[file_path]

        for i, root_name in enumerate(file_roots):
            is_last = i == len(file_roots) - 1
            lines.extend(
                render_class_block(
                    root_name,
                    classes,
                    children_map,
                    unresolved_bases_map,
                    include_private=include_private,
                    classes_only=classes_only,
                    prefix="",
                    is_last=is_last,
                )
            )

    visited: Set[str] = set()
    for root_name in roots:
        collect_reachable(root_name, children_map, visited)

    missing = sorted(set(classes) - visited)
    if missing:
        lines.append("")
        lines.append("Unattached / unresolved classes")
        lines.append("-" * 28)
        for i, class_name in enumerate(missing):
            lines.extend(
                render_class_block(
                    class_name,
                    classes,
                    children_map,
                    unresolved_bases_map,
                    include_private=include_private,
                    classes_only=classes_only,
                    prefix="",
                    is_last=i == len(missing) - 1,
                )
            )

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a text-based class inheritance diagram from Python files in a folder."
    )
    parser.add_argument("folder", help="Folder containing Python files")
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Also scan subfolders recursively",
    )
    parser.add_argument(
        "--include-private",
        action="store_true",
        help="Include private methods and class variables starting with '_'",
    )
    parser.add_argument(
        "--classesonly",
        action="store_true",
        help="Only list class names and inheritance, hide methods and class variables",
    )
    parser.add_argument(
        "--output",
        help="Write output to a text file instead of only printing",
    )

    args = parser.parse_args()

    folder = Path(args.folder).resolve()
    if not folder.exists():
        print(f"Error: folder does not exist: {folder}")
        return 1

    if not folder.is_dir():
        print(f"Error: not a folder: {folder}")
        return 1

    files = collect_python_files(folder, recursive=args.recursive)
    if not files:
        print("No .py files found.")
        return 0

    classes = parse_classes(folder, files)
    diagram = render_diagram(
        classes,
        include_private=args.include_private,
        classes_only=args.classesonly,
    )

    print(diagram)

    if args.output:
        output_path = Path(args.output).resolve()
        output_path.write_text(diagram, encoding="utf-8")
        print(f"\nWritten to: {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())