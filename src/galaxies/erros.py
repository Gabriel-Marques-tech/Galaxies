class ErroGalaxies(Exception):
    """Erro de domínio, com mensagem pensada para o agente do usuário ler."""


class ProjetoNaoEncontrado(ErroGalaxies):
    def __init__(self, nome: str):
        super().__init__(f"Projeto '{nome}' não existe. Crie com criar_projeto.")


class ProjetoJaExiste(ErroGalaxies):
    def __init__(self, nome: str):
        super().__init__(f"Projeto '{nome}' já existe. Escolha outro nome.")


class ConfigInvalida(ErroGalaxies):
    pass


class DependenciaAusente(ErroGalaxies):
    def __init__(self, nome: str):
        super().__init__(f"Dependência externa '{nome}' não configurada (ver .env).")


class CanalNaoEncontrado(ErroGalaxies):
    def __init__(self, ref: str):
        super().__init__(f"Canal '{ref}' não encontrado no YouTube.")
