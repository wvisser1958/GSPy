"""
GSPy Simulation API — Interface for Gas Turbine Performance Models

The GSPy API provides a structured, function-based interface for
executing gas turbine performance models and integrating their 
results into broader workflows. Designed with interoperability in 
mind, this layer follows the principles outlined in SAE ARP4868 
without claiming official affiliation. It enables developers to 
initialize models, configure inputs, run simulations, and retrieve 
outputs in a consistent, programmatic manner. In addition to core 
simulation functions, the API includes logging controls for 
traceability and a base model class that supports inheritance, 
allowing users to extend functionality for custom applications. 
By abstracting complexity behind a clean interface, the GSPy API 
ensures that performance modeling can be seamlessly embedded into 
system performance models that require gas turbine performance 
simulation results.

Typical usage:
    from gspy.api import (
        initProg, run, terminate, activateLog, closeLog, parseString,
        getModelComponentsList, BaseGasTurbineModel
    )

    handle = initProg(model="turbojet")
    activateLog(filename="turbojet.log")
    result = run()
    terminate()
"""

from .gspy_api import (
    initProg,
    activateLog,
    closeLog,
    run,
    terminate,
    parseString,
    getModelComponentsList,
    # Optionally expose all get/set/define/parse helpers:
    defineDataList,
    getArraySize1D, getArraySize2D, getArraySize3D,
    getD, getD1D, getD1Dentry, getD2Dentry, getD3Dentry,
    getDataListD, getDataListF, getDataListI,
    getDataType, getDescription, getErrorMsg,
    getF, getF1D, getF1Dentry, getF2Dentry, getF3Dentry,
    getI, getI1D, getI1Dentry, getI2Dentry, getI3Dentry,
    getS, getS1Dentry, getS2Dentry, getS3Dentry,
    getSeverityMax, getUnits, isValidParamName,
    parseEfile, parseFile,
    setD, setD1D, setD1Dentry, setD2Dentry, setD3Dentry,
    setDataListD, setDataListF, setDataListI,
    setF, setF1D, setF1Dentry, setF2Dentry, setF3Dentry,
    setI, setI1D, setI1Dentry, setI2Dentry, setI3Dentry,
    setS, setS1Dentry, setS2Dentry, setS3Dentry,
)
from .base_model import BaseGasTurbineModel

__all__ = [
    # Main ARP4868 API
    "initProg", "activateLog", "closeLog", "run", "terminate", "parseString",
    "getModelComponentsList",
    # Data/parameter helpers
    "defineDataList",
    "getArraySize1D", "getArraySize2D", "getArraySize3D",
    "getD", "getD1D", "getD1Dentry", "getD2Dentry", "getD3Dentry",
    "getDataListD", "getDataListF", "getDataListI",
    "getDataType", "getDescription", "getErrorMsg",
    "getF", "getF1D", "getF1Dentry", "getF2Dentry", "getF3Dentry",
    "getI", "getI1D", "getI1Dentry", "getI2Dentry", "getI3Dentry",
    "getS", "getS1Dentry", "getS2Dentry", "getS3Dentry",
    "getSeverityMax", "getUnits", "isValidParamName",
    "parseEfile", "parseFile",
    "setD", "setD1D", "setD1Dentry", "setD2Dentry", "setD3Dentry",
    "setDataListD", "setDataListF", "setDataListI",
    "setF", "setF1D", "setF1Dentry", "setF2Dentry", "setF3Dentry",
    "setI", "setI1D", "setI1Dentry", "setI2Dentry", "setI3Dentry",
    "setS", "setS1Dentry", "setS2Dentry", "setS3Dentry",
    # Base class for custom models
    "BaseGasTurbineModel"
]
