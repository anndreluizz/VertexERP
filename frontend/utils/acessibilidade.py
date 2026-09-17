import sys


def movimento_reduzido() -> bool:
    """Reflete a preferência de acessibilidade do Windows ("Mostrar
    animações" em Configurações > Acessibilidade > Efeitos visuais) --
    equivalente ao prefers-reduced-motion da web, que o Qt não expõe
    direto (QStyleHints não tem esse campo até a versão do PySide6
    instalada aqui, 6.11). Fora do Windows, ou se a chamada da API
    falhar por qualquer motivo, assume False (anima normalmente) --
    uma checagem de acessibilidade não deveria nunca travar a UI."""

    if sys.platform != "win32":
        return False

    try:
        import ctypes

        SPI_GETCLIENTAREAANIMATION = 0x1042
        habilitado = ctypes.c_bool()
        ok = ctypes.windll.user32.SystemParametersInfoW(
            SPI_GETCLIENTAREAANIMATION, 0, ctypes.byref(habilitado), 0
        )
        if not ok:
            return False
        return not habilitado.value
    except Exception:
        return False
