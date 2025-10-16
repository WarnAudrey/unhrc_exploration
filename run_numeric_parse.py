import json
from pathlib import Path

from endf_mf8_mt457_numeric_parser import ENDFNumericDecayParser


def sci(v):
    if isinstance(v, float):
        return f"{v:.6e}"
    if isinstance(v, (list, tuple)) and v and isinstance(v[0], (float, int)):
        return [f"{float(x):.6e}" for x in v]
    return v


def format_dict(d):
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out[k] = format_dict(v)
        elif isinstance(v, list):
            out[k] = [format_dict(x) if isinstance(x, dict) else sci(x) for x in v]
        elif isinstance(v, tuple):
            out[k] = tuple(sci(list(v)))
        else:
            out[k] = sci(v)
    return out


def main():
    text = Path("sample_endf_input.txt").read_text(encoding="utf-8")
    parser = ENDFNumericDecayParser(text)
    data = parser.parse_file("sample_endf_input.txt")
    formatted = format_dict(data)
    print(json.dumps(formatted, indent=2))


if __name__ == "__main__":
    main()
