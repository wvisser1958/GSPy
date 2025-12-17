from gspy.api import ARP4868

# Initialize the model
print(ARP4868.initProg(model="turbojet", mode='DP'))

# Optionally activate logging
print(ARP4868.activateLog(filename="turbojet.log", mode="w"))

# Run the model
result = ARP4868.run()
print("Run complete:", result)

# Get the model components
result = ARP4868.parseString(function="getModelComponentsList")
print("parString complete:", result)

# Optionally close the log
# print(ARP4868.closeLog())

# Terminate model
ARP4868.terminate()