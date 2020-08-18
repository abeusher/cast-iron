# Cast Iron Documentation

## Getting Started

* Install [Pyenv]
* Install python
```bash
$ pyenv install
```
* Install [Poetry]
* Install dependencies
```bash
$ poetry install
```

## Locally Serving the Docs

Activate your [Poetry] shell:
```bash
$ poetry shell
```

From there the process is the same as in the [MkDocs] and in the [Material MkDocs] documentation:
```bash
$ mkdocs serve
```

Additionaly, the docs can be served locally using [Make]:
```bash
$ make shell
$ make serve
```

## Building the Docs for Deployment

Activate your [Poetry] shell:
```bash
$ poetry shell
```

From there the process is the same as in the [MkDocs] and in the [Material MkDocs] documentation:
```bash
$ mkdocs build
```

Additionaly, the docs can be served locally using [Make]:
```bash
$ make shell
$ make build
```

The built documentation is found in the `site` directory.


[Pyenv]: https://github.com/pyenv/pyenv
[Poetry]: https://python-poetry.org/
[MkDocs]: https://www.mkdocs.org/
[Material MkDocs]: https://squidfunk.github.io/mkdocs-material/
