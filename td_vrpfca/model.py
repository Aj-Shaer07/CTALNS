"""Model-layer compatibility module for the combined OT PROJ codebase.

Objective 1 already owns the main TD-VRPFCA representation in model.py.
In the MILP extension, the Gurobi formulation is kept separately in milp.py
so the Objective-1 model is not replaced.
"""

from .loader import Instance, Vehicle

__all__ = ["Instance", "Vehicle"]
