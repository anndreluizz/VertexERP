"""Executa uma chamada de rede (ou qualquer função bloqueante) fora da
thread principal do Qt, devolvendo o resultado/erro pra ela via sinal.

Hoje NENHUMA chamada de rede do app roda numa thread separada --
services/api.py usa requests.Session síncrono direto, e todo clique
que dispara uma chamada trava a janela inteira até a resposta chegar
(ou pra sempre, se a rede cair no meio, ver timeout adicionado em
services/api.py). rodar_em_thread() é o jeito padrão de sair desse
padrão sem reescrever cada tela do zero.

Uso (o `parent` PRECISA ser um QWidget/QObject vivo, e os callbacks
PRECISAM ser métodos vinculados a um QObject -- ver nota no fim):

    self._thread = rodar_em_thread(
        self,
        listar_clientes,
        loja_id,
        ao_sucesso=self._ao_carregar_sucesso,
        ao_erro=self._ao_carregar_erro,
        ao_finalizar=self._ao_carregar_finalizar,
    )
"""

from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QObject, QThread, Signal


def em_paralelo(*chamadas):
    """Roda varias chamadas de rede independentes entre si ao mesmo
    tempo em vez de em fila, e devolve os resultados na mesma ordem.

    Uso -- DENTRO de uma funcao que ja roda na worker thread (ver
    rodar_em_thread acima), quando ela mesma precisa fazer N chamadas
    que nao dependem uma da outra:

        usuario, dados = em_paralelo((me,), (configuracoes,))
        vendas, produtos = em_paralelo(
            (listar_vendas, loja_id), (listar_produtos,)
        )

    Cada item e' uma tupla (func, *args). Numa conexao de latencia
    alta (ex.: terminal remoto via VPN, ver Tailscale sem UPnP), isso
    e' a diferenca entre "soma das N idas-e-voltas" e "o tempo da mais
    lenta das N". Nao tem restricao de metodo-vinculado igual
    rodar_em_thread -- nao mexe com sinal do Qt, so' concurrent.futures
    puro, entao lambda/closure funciona normalmente aqui."""

    with ThreadPoolExecutor(max_workers=len(chamadas)) as executor:
        futuros = [executor.submit(func, *args) for func, *args in chamadas]
        return [futuro.result() for futuro in futuros]


class _Worker(QObject):

    sucesso = Signal(object)
    erro = Signal(Exception)
    finalizado = Signal()

    def __init__(self, func, args, kwargs):
        super().__init__()
        self._func = func
        self._args = args
        self._kwargs = kwargs

    def rodar(self):
        try:
            resultado = self._func(*self._args, **self._kwargs)
        except Exception as erro:
            self.erro.emit(erro)
        else:
            self.sucesso.emit(resultado)
        finally:
            self.finalizado.emit()


class _Limpeza(QObject):
    """Vive na thread da GUI (filha do parent), entao o Qt entrega
    thread.finished pra ela em fila, fora da worker thread."""

    def __init__(self, parent, thread):
        super().__init__(parent)
        self._thread = thread

    def limpar(self):
        ativas = getattr(self.parent(), "_threads_ativas", [])
        if self._thread in ativas:
            ativas.remove(self._thread)
        self._thread = None
        self.deleteLater()


def rodar_em_thread(
    parent,
    func,
    *args,
    ao_sucesso=None,
    ao_erro=None,
    ao_finalizar=None,
    **kwargs,
):
    """Roda `func(*args, **kwargs)` numa QThread separada.

    `ao_sucesso(resultado)`, `ao_erro(excecao)` e `ao_finalizar()` sao
    chamados de volta na thread principal -- IMPORTANTE: precisam ser
    métodos vinculados a um QObject (ex.: `self.algum_metodo`, não uma
    lambda/função solta). É a instância de QObject do método que o Qt
    usa pra saber "isso pertence à thread principal, entrega em fila"
    em vez de rodar o callback dentro da própria worker thread (o que
    quebraria qualquer chamada a widget lá dentro -- Qt não permite
    mexer em widget fora da thread da GUI).

    A QThread retornada é guardada em `parent._threads_ativas` pra não
    ser coletada pelo GC do Python no meio da execução (PySide6 não
    seguraria essa referência sozinho, e uma QThread coletada enquanto
    roda derruba o processo)."""

    for nome, callback in (
        ("ao_sucesso", ao_sucesso),
        ("ao_erro", ao_erro),
        ("ao_finalizar", ao_finalizar),
    ):
        # falha alto e na hora em vez de silencioso: uma lambda/funcao
        # solta aqui RODA NA WORKER THREAD (confirmado empiricamente --
        # o Qt so' sabe pra qual thread entregar em fila quando o
        # receptor da conexao e' um QObject de verdade, o que um
        # metodo vinculado expoe via __self__ e uma lambda nao).
        # Ja aconteceu uma vez (login.py mexendo em widget fora da GUI
        # thread) antes dessa checagem existir.
        if callback is not None and not hasattr(callback, "__self__"):
            raise TypeError(
                f"{nome} precisa ser um metodo vinculado a um QObject "
                f"(ex.: self.algum_metodo) -- recebido {callback!r}, que "
                f"rodaria na worker thread em vez da GUI. Ver docstring "
                f"de rodar_em_thread."
            )

    thread = QThread(parent)
    worker = _Worker(func, args, kwargs)
    worker.moveToThread(thread)

    # moveToThread NAO da' ownership pro QThread (isso so' existe pra
    # relacao pai/filho normal, que exige mesma thread -- nao rola
    # aqui). Sem guardar `worker` em algum lugar, era o unico dono
    # dessa referencia o escopo local desta funcao: assim que
    # rodar_em_thread() retornava, o GC do Python coletava `worker`
    # antes do thread.started sequer disparar (achado rodando o teste
    # de fumaça -- thread.started nunca chegava a chamar rodar()).
    # Prender em `thread` mantem worker vivo pelo mesmo tempo que a
    # thread (ja' segurada por parent._threads_ativas abaixo).
    thread._worker = worker

    thread.started.connect(worker.rodar)

    if ao_sucesso:
        worker.sucesso.connect(ao_sucesso)
    if ao_erro:
        worker.erro.connect(ao_erro)
    if ao_finalizar:
        worker.finalizado.connect(ao_finalizar)

    worker.finalizado.connect(thread.quit)
    worker.finalizado.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)

    if not hasattr(parent, "_threads_ativas"):
        parent._threads_ativas = []
    parent._threads_ativas.append(thread)

    # tira da lista quando termina -- pela thread da GUI. Antes era uma
    # funcao solta ligada em thread.finished, que roda NA worker thread:
    # soltar ali a ultima referencia da QThread/worker derrubava o
    # sistema sem log (0xc0000409) logo depois de salvar uma despesa.
    thread.finished.connect(_Limpeza(parent, thread).limpar)

    thread.start()
    return thread
