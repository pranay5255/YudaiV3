from __future__ import annotations
from pathlib import Path
from typing import Any, get_args, get_origin, Union
from models import CSVMetadata, ProjectConfig, PromptContext, RunCLIRequest, RunCLIResponse

PY_TO_TS = {str: 'string', int: 'number', float: 'number', bool: 'boolean', Any: 'unknown'}

def ts_type(tp: Any) -> str:
    origin = get_origin(tp)
    if origin is None:
        return PY_TO_TS.get(tp, 'any')
    if origin in (list, list[Any]):
        return f"{ts_type(get_args(tp)[0])}[]"
    if origin in (dict, dict[Any, Any]):
        key, val = get_args(tp)
        return f"Record<{ts_type(key)}, {ts_type(val)}>"
    if origin is Union:
        args = [a for a in get_args(tp)]
        if type(None) in args:
            args.remove(type(None))
            return f"{ts_type(args[0])} | null"
        return ' | '.join(ts_type(a) for a in args)
    return 'any'

def generate(model) -> str:
    lines = [f"export interface {model.__name__} {{"]
    for name, field in model.model_fields.items():
        lines.append(f"  {name}: {ts_type(field.annotation)};")
    lines.append("}\n")
    return '\n'.join(lines)

models = [CSVMetadata, ProjectConfig, PromptContext, RunCLIRequest, RunCLIResponse]
content = "\n".join(generate(m) for m in models)
output_path = Path(__file__).resolve().parent.parent / 'src' / 'pydantic-types.ts'
output_path.write_text(content)
print(f'Written {output_path}')
