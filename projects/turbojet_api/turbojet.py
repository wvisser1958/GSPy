
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Authors
#   Wilfried Visser
#   Oscar Kogenhop

from gspy.api.base_model import BaseGasTurbineModel

class Turbojet(BaseGasTurbineModel):
    """Input schema for turbojet engine simulation (declarative, no core imports)."""

    def __init__(self):
        super().__init__("turbojet")

    def run(self):
        super().run()
        self.save_output_csv()
        print("end of running turbojet simulation")

    def build_model(self):
        # Use the default maps folder in the root of the model file (self.map_path)
        comp_map = (self.map_path / "compmap.map").as_posix()
        turb_map = (self.map_path / "turbimap.map").as_posix()
        return [
            # type, name, args (excluding name, which is always first)
            {"type": "Ambient", "name": "Ambient", "args": [0, 0, 0, 0, None, None]},
            {"type": "Control", "name": "Fuel Controller", "args": ['', 0.38, 0.38, 0.08, -0.01, None]},
            {"type": "Inlet", "name": "Inlet", "args": ['', None, 0, 2, 19.9, 1]},
            {"type": "Compressor", "name": "Compressor", "args": [comp_map, None, 2, 3, 1, 16540, 0.825, 1, 0.75, 6.92, 'GG', None]},
            {"type": "Combustor", "name": "Combustor", "args": ['', 'Fuel Controller', 3, 4, 0.38, None, 1, 1, None, 43031, 1.9167, 0, None, None]},
            {"type": "Turbine", "name": "Turbine", "args": [turb_map, None, 4, 5, 1, 16540, 0.88, 1, 0.50943, 0.99, 'GG', None]},
            {"type": "Duct", "name": "Exhaust Duct", "args": ['', None, 5, 7, 1.0]},          
            {"type": "ExhaustNozzle", "name": "Exhaust Nozzle", "args": ['', None, 7, 8, 9, 1, 1, 1]}
        ]