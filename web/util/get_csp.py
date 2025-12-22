import secrets


def get_csp() -> tuple[str, str]:
    nonce = secrets.token_urlsafe(16)
    text = (
        "default-src 'none'; frame-ancestors 'none'; object-src 'none'; base-uri 'none'; script-src 'nonce-{}' "
        "'strict-dynamic'; style-src 'nonce-{}'; require-trusted-types-for 'script'; "
        "img-src 'nonce-{}' data:; script-src-attr 'nonce-{}'; frame-src https://challenges.cloudflare.com;"
    )
    text = text.format(nonce, nonce, nonce, nonce)
    return text, nonce
