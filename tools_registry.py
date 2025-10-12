from typing import Dict, Any, Callable, List
from data_processor import (
    calculate_velocity_trend, 
    calculate_sprint_completion, 
    calculate_capacity_utilization, 
    calculate_defect_density, 
    calculate_defect_stage_distribution, 
    get_raid_summary
)
import pandas as pd # Needed for type hinting in Tool definitions

# Define a structure for our tools for clarity
class Tool:
    def __init__(self, name: str, description: str, func: Callable, parameters: Dict[str, Any]):
        self.name = name
        self.description = description
        self.func = func
        self.parameters = parameters # JSON schema for parameters

    def get_spec(self) -> Dict[str, Any]:
        """
        Returns the tool specification in a format suitable for Gemini's function calling.
        This now returns a single function declaration dictionary.
        """
        # Filter out the 'optional' key if it exists, as it's not supported in Gemini's schema.
        # Also, ensure 'default' is present if intended, but not 'optional'.
        cleaned_parameters = {}
        required_params_list = []
        for param_name, param_spec in self.parameters.items():
            cleaned_spec = {k: v for k, v in param_spec.items() if k != 'optional'}
            cleaned_parameters[param_name] = cleaned_spec
            if "default" not in param_spec: # If no default, it's truly required from the LLM
                required_params_list.append(param_name)

        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": cleaned_parameters,
                "required": required_params_list # Only list parameters that are truly mandatory for the LLM to provide.
            }
        }

# --- TOOL REGISTRY ---
# This dictionary will hold all the callable tools and their specifications.
# The keys should match the function names exactly for direct invocation.

TOOL_REGISTRY: Dict[str, Tool] = {
    "calculate_velocity_trend": Tool(
        name="calculate_velocity_trend",
        description="Calculates the velocity trend (completed story points) for each sprint over time. Requires the pre-processed JIRA DataFrame.",
        func=calculate_velocity_trend,
        parameters={
            "df_jira": {"type": "object", "description": "The pre-processed JIRA DataFrame. (Provided by orchestrator)"}
        }
    ),
    "calculate_sprint_completion": Tool(
        name="calculate_sprint_completion",
        description="Calculates sprint goal completion by comparing committed vs. completed story points for each sprint. Requires the pre-processed JIRA DataFrame.",
        func=calculate_sprint_completion,
        parameters={
            "df_jira": {"type": "object", "description": "The pre-processed JIRA DataFrame. (Provided by orchestrator)"}
        }
    ),
    "calculate_capacity_utilization": Tool(
        name="calculate_capacity_utilization",
        description="Calculates capacity utilization for individual assignees across recent sprints. Requires the pre-processed JIRA DataFrame.",
        func=calculate_capacity_utilization,
        parameters={
            "df_jira": {"type": "object", "description": "The pre-processed JIRA DataFrame. (Provided by orchestrator)"},
            "num_sprints": {"type": "integer", "description": "Number of most recent sprints to consider (default 5).", "default": 5} # Removed "optional": True
        }
    ),
    "calculate_defect_density": Tool(
        name="calculate_defect_density",
        description="Calculates the defect density (number of defects vs. number of stories) per sprint. Requires the pre-processed JIRA and Defects DataFrames.",
        func=calculate_defect_density,
        parameters={
            "df_jira": {"type": "object", "description": "The pre-processed JIRA DataFrame. (Provided by orchestrator)"},
            "df_defects": {"type": "object", "description": "The pre-processed Defects DataFrame. (Provided by orchestrator)"}
        }
    ),
    "calculate_defect_stage_distribution": Tool(
        name="calculate_defect_stage_distribution",
        description="Analyzes the distribution of open defects across different phases (e.g., SIT, UAT, Prod). Requires the pre-processed Defects DataFrame.",
        func=calculate_defect_stage_distribution,
        parameters={
            "df_defects": {"type": "object", "description": "The pre-processed Defects DataFrame. (Provided by orchestrator)"}
        }
    ),
    "get_raid_summary": Tool(
        name="get_raid_summary",
        description="Provides a summary of open RAID (Risks, Assumptions, Issues, Dependencies) items, including overdue items. Requires the pre-processed RAID DataFrame.",
        func=get_raid_summary,
        parameters={
            "df_raid": {"type": "object", "description": "The pre-processed RAID DataFrame. (Provided by orchestrator)"}
        }
    )
}

def get_all_tool_specs() -> List[Dict[str, Any]]:
    """
    Returns a list of all tool specifications (function declarations) for Gemini.
    """
    all_specs = []
    for tool_obj in TOOL_REGISTRY.values():
        all_specs.append(tool_obj.get_spec())
    return all_specs
