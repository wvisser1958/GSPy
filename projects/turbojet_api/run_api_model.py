from gspy.api import gspy_api

# Initialize the model
print(gspy_api.initProg(model="turbojet", mode='DP'))

# Optionally activate logging
print(gspy_api.activateLog(filename="turbojet.log", mode="w"))

# Run the model
result = gspy_api.run()
print("Run complete:", result)

# Get the model components
result = gspy_api.parseString(function="get_model_components_list")
print("parString complete, result:\n", result)
# Get the model output parameters
result = gspy_api.parseString(function="get_output_parameter_names")
print("parString complete, result:\n", result)
result = gspy_api.isValidParamName(parameter="A8_geom")
print(result)

temperatures = "T0, T2, T3, T4, T5, T9"
dispatch = gspy_api.defineDataList(name="temperatures", params=temperatures,
                          description="Core & turbine temperature sensors",
                          category="APU")
print(dispatch)


# Optionally close the log
# print(ARP4868.closeLog())

# Terminate model
gspy_api.terminate()