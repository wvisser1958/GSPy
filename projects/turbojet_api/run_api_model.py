from gspy.api import gspy_api

# Initialize the model
print(gspy_api.initProg(model="turbojet", mode='DP'))

# Optionally activate logging
print(gspy_api.activateLog(filename="turbojet.log", mode="w"))

# Run the model
result = gspy_api.run()
print("Run complete:", result)

# Get the model components
result = gspy_api.parseString(function="getModelComponentsList")
print("parString complete:", result)

# Optionally close the log
# print(ARP4868.closeLog())

# Terminate model
gspy_api.terminate()