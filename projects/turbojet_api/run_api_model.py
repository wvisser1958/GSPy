from gspy.api import gspy_api

# Initialize the model
print("\n", gspy_api.initProg(model="turbojet", mode='DP'))

# Optionally activate logging
print("\n", gspy_api.activateLog(filename="turbojet.log", mode="w"))

# Run the model
result = gspy_api.run()
print("\nRun complete:", result)

# Get the model components
result = gspy_api.parseString(function="get_model_components_list")
print("\nparString complete, result:\n", result)
# Get the model output parameters
result = gspy_api.parseString(function="get_output_parameter_names")
print("\nparString complete, result:\n", result)
result = gspy_api.isValidParamName(parameter="A8_geom")
print("\n", result)

temperatures = "T0, T2, T3, T4, T5, T9"
dispatch = gspy_api.defineDataList(name="temperatures", params=temperatures,
                          description="Gas turbine temperatures dataset for quick reference",
                          category="Turbojet")
print("\n", dispatch)

resp = gspy_api.getDataListD(name="temperatures", source="e.g. OutputTableResults")
print("\n", resp)

result = gspy_api.getD(parameter='A8_geom')
print("\n", result)

# Optionally close the log
print("\n", gspy_api.closeLog())

# Terminate model
gspy_api.terminate()