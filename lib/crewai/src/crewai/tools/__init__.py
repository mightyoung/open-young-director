from crewai.tools.base_tool import BaseTool, EnvVar, tool


__all__ = [
    "BaseTool",
    "EnvVar",
    "tool",
]


# ComfyUI tools (lazy import to avoid hard dependency)
def __getattr__(name: str):
    if name == "comfyui_image_tool":
        from crewai.tools.comfyui_tools import comfyui_image_tool

        return comfyui_image_tool
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
