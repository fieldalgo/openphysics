# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""simcase.studio - the browser UI: a FastAPI server and a single-page client.

Optional. It needs the ``studio`` extra (``pip install simcase[studio]``); the
base install stays headless, so a batch or HPC user never pulls a web stack.

    $ simcase-studio                 # or: python -m simcase.studio
    $ python -m simcase.studio --port 9000 --no-browser

The boundary is deliberate and strict: this subpackage may use only simcase's
public API (the names in ``simcase.__all__``), never a module underneath it.
That is what keeps lifting it back out into its own distribution a move rather
than a rewrite. When the UI needs something simcase does not export, promote it
to the public API on purpose instead of reaching in.
"""

from .server import app, main

__all__ = ["app", "main"]
