from litestar import MediaType
from litestar.response import Template

from web import constants
from web.util import get_csp


def html_template(
    template_name: str,
    context: dict = None,
    *,
    status_code: int = 200,
    csp_allow_discord_cdn_in_images: bool = False,
) -> Template:
    if context is None:
        context = {}

    csp, nonce = get_csp(
        csp_allow_discord_cdn_in_images=csp_allow_discord_cdn_in_images
    )
    context["csp_nonce"] = nonce
    context["site_name"] = constants.SITE_NAME
    context["is_production"] = constants.IS_PRODUCTION
    return Template(
        template_name=template_name,
        context=context,
        headers={"content-security-policy": csp},
        media_type=MediaType.HTML,
        status_code=status_code,
    )
