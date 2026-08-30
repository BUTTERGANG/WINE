"""Custom template rendering — bypasses Jinja2 cache hash bug with Starlette 1.6."""

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from starlette.templating import _TemplateResponse

from backend.config import BASE_DIR

templates_dir = BASE_DIR / "backend" / "templates"

# Create a fresh environment with NO cache to avoid the hash bug
_env = Environment(
    loader=FileSystemLoader(str(templates_dir)),
    autoescape=select_autoescape(["html", "xml"]),
    cache_size=0,  # Disable cache to avoid hash-key bug in Jinja2/Starlette
)


class Templates:
    """Stand-in for Starlette's Jinja2Templates that works around the cache bug."""

    def TemplateResponse(
        self,
        name: str,
        context: dict[str, Any],
        status_code: int = 200,
    ) -> _TemplateResponse:
        template = _env.get_template(name)
        return _TemplateResponse(
            template,
            context,
            status_code=status_code,
        )


templates = Templates()