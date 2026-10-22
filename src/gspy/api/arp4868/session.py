from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class Session:
    """Holds the current Engine Program session state."""

    model: Any = None
    initialized: bool = False

    # API-level error reporting
    last_error_msg: str = ""
    last_funct_status: int = 0

    # Engine-program severity (0-9, 99, etc.). If unknown: 999.
    severity_max: int = 0

    # logging
    log: Any = None  # file-like

    # DataList support: listID -> (dataType, [paramName, ...])
    data_lists: Dict[int, Tuple[str, List[str]]] = field(default_factory=dict)
    _next_list_id: int = 1

    def next_list_id(self) -> int:
        i = self._next_list_id
        self._next_list_id += 1
        return i

    def reset(self) -> None:
        self.model = None
        self.initialized = False
        self.last_error_msg = ""
        self.last_funct_status = 0
        self.severity_max = 0
        self.data_lists.clear()
        self._next_list_id = 1
        self.close_log()

    def write_log(self, line: str) -> None:
        if not self.log:
            return
        try:
            self.log.write(line+'\n')
            if hasattr(self.log, 'flush'):
                self.log.flush()
        except Exception:
            # logging must never crash the API
            pass

    def close_log(self) -> None:
        if self.log and self.log not in (sys.stdout, sys.stderr):
            try:
                self.log.close()
            except Exception:
                pass
        self.log = None
