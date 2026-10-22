"""GSPy ARP4868-style function-based API (Python prefix: py4868*)

This is a lightweight framework that mirrors the ARP4868 function suite while
remaining Pythonic and easy to embed into the GSPy repo.

Key design choice for this package version:
- No parameter registry.
- All *get* operations query the last row of the model OutputTable DataFrame
  (column name == paramName).

The calling program is responsible for:
- py4868initProg(...)
- providing inputs via py4868set*() and/or py4868parseFile/py4868parseString
- py4868run()
- retrieving scalar values from OutputTable using py4868get*
- py4868terminate()

Not affiliated with or endorsed by SAE.
"""

from gspy.api.arp4868.functions import (
    py4868initProg,
    py4868terminate,
    py4868run,
    py4868activateLog,
    py4868closeLog,
    py4868getErrorMsg,
    py4868getSeverityMax,
    py4868isValidParamName,
    py4868getDataType,
    py4868getUnits,
    py4868getDescription,
    py4868getD,
    py4868getF,
    py4868getI,
    py4868getS,
    py4868setD,
    py4868setF,
    py4868setI,
    py4868setS,
    py4868defineDataList,
    py4868getDataListD,
    py4868getDataListF,
    py4868getDataListI,
    py4868setDataListD,
    py4868setDataListF,
    py4868setDataListI,
    py4868parseFile,
    py4868parseEfile,
    py4868parseString,
    py4868getArraySize1D,
    py4868getArraySize2D,
    py4868getArraySize3D,
    py4868getD1D,
    py4868getF1D,
    py4868getI1D,
    py4868setD1D,
    py4868setF1D,
    py4868setI1D,
)

__all__ = [name for name in globals().keys() if name.startswith('py4868')]
