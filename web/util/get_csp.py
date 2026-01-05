import secrets


def get_csp(*, csp_allow_discord_cdn_in_images: bool = False) -> tuple[str, str]:
    nonce = secrets.token_urlsafe(16)
    text = (
        "default-src 'none'; frame-ancestors 'none'; object-src 'none'; base-uri 'none'; "
        f"script-src 'nonce-{nonce}' "
        f"'strict-dynamic'; style-src 'nonce-{nonce}'; require-trusted-types-for 'script'; "
        f"img-src 'nonce-{nonce}' data: 'self'"
        f"{' https://cdn.discordapp.com' if csp_allow_discord_cdn_in_images else ''}; "
        f"script-src-attr 'nonce-{nonce}'; frame-src https://challenges.cloudflare.com;"
    )
    return text, nonce
