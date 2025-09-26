"""AI Solver package for YudaiV3."""

__all__ = ["AISolverAdapter"]


def __getattr__(name: str):
    if name == "AISolverAdapter":
        from .ai_solver import AISolverAdapter as _AISolverAdapter

        return _AISolverAdapter
    raise AttributeError(name)
