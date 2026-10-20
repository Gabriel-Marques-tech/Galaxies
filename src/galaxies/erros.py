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


class CanalForaDaBase(ErroGalaxies):
    def __init__(self, canal_id: str):
        super().__init__(
            f"Canal '{canal_id}' não está na base do modelo. Rode adicionar_canal com ele e "
            "depois treinar, para o modelo conhecer o histórico do canal."
        )


class CotaEsgotada(ErroGalaxies):
    """Limite de uso de um serviço externo acabou (ex.: cota diária gratuita)."""
