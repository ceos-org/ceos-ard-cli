import pathlib as path

from .util import read_pfs, read_template

def validate(verbose):

    def log(file, error = None):
        if verbose or error is not None:
            message = str(error) if error is not None else "OK"
            print(f"- {file.stem}: {message}")

    def check(folder, fn):
        print(f"Validating {folder}")
        files = get_all_files(folder)
        for file in files:
            error = None
            try:
                fn(file)
            except Exception as e:
                error = e
            finally:
                log(file, error)

    check("pfs", lambda file: read_pfs(file.parent.stem))

    # todo: check all files, even if unused
    # todo: warn/error if files are unused

    # todo: check more, this check is only very high-level jinja-based
    print("Validating PFS template")
    try:
        read_template()
    except Exception as e:
        log("templates/template.md", e)


def get_all_files(folder, ext = '.yaml'):
    files = []
    for f in path.Path(folder).iterdir():
        if f.is_file() and f.name.endswith(ext):
            files.append(f)
        elif f.is_dir():
            files += get_all_files(f, ext)

    return files
