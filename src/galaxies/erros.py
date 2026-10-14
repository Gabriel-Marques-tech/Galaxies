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
