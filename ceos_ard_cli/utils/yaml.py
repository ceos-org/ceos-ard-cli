from pathlib import Path

import strictyaml

from ..utils.files import read_file

# Each file is parsed once per schema; callers get copies, as they may change the data
YAML_CACHE = {}
# The files being read right now (path and whether its result may be cached), to stop at circular references
_READING = []


def read_yaml(file, schema, base_path):
    if not schema:
        raise (ValueError(f"Schema is not provided for {file}"))
    key = (str(Path(file)), schema, str(Path(base_path)))
    if key in YAML_CACHE:
        return copy_data(YAML_CACHE[key])
    path = Path(file).resolve()
    reading = [p for p, _ in _READING]
    if path in reading:
        chain = [p.name for p in reading[reading.index(path) :]] + [path.name]
        raise ValueError(f"Circular reference: {' -> '.join(chain)}")
    frame = [path, True]
    _READING.append(frame)
    try:
        data = to_py(strictyaml.load(read_file(file), schema(file, base_path)))
    finally:
        _READING.pop()
    if frame[1]:
        YAML_CACHE[key] = data
    return copy_data(data)


def skip_if_being_read(file):
    """True for a file that is being read, which validates it; the files read since then depend on its outcome."""
    path = Path(file).resolve()
    for index, (reading, _) in enumerate(_READING):
        if reading == path:
            # Their result is only valid if this file turns out to be valid, so they aren't cached
            for frame in _READING[index + 1 :]:
                frame[1] = False
            return True
    return False


def copy_data(data):
    if isinstance(data, dict):
        return {key: copy_data(value) for key, value in data.items()}
    if isinstance(data, list):
        return [copy_data(value) for value in data]
    if data is None or isinstance(data, (str, bool, int, float)):
        return data
    # Anything else could be changed by one caller and leak into the data of another
    raise TypeError(f"Unexpected type in YAML data: {type(data).__name__}")


def to_py(data):
    if isinstance(data, strictyaml.Map):
        return {k: to_py(v) for k, v in data.items()}
    elif isinstance(data, strictyaml.Seq):
        return [to_py(v) for v in data]
    else:
        if hasattr(data, "data"):
            return data.data
        else:
            return data
