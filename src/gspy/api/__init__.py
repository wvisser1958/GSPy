
"""
GSPy API Layer — ARP4868-compliant interface

This package provides the function-based API for gas turbine simulation models,
conforming to the SAE ARP4868 standard. It exposes the main ARP4868 functions,
logging controls, and the base model class for inheritance.

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

from .ARP4868 import (
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
